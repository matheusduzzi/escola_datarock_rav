"""Plano B do assistente: decide se ele responde, diz que não sabe ou passa para uma pessoa.

O fluxo tem três paradas, nessa ordem:

  1. Os trechos. Tira o que não vale (rascunho, vencido, fora do perfil). Se não sobrou
     trecho, diz que não sabe, e o modelo nem seria chamado.
  2. O rascunho do modelo. Se uma fonte citada tem outra fonte que vale, sobre o mesmo
     assunto, dizendo outra coisa, passa para uma pessoa. Fora isso, cada frase cita um trecho
     que valeu, e cada número está no trecho citado ou na pergunta. Se não, o rascunho não sai
     e o assistente diz que não sabe.
  3. Quem resolve. O cliente pediu uma pessoa, o trecho usado diz que uma pessoa decide, ou o
     assistente não sabe e a conversa tem um pedido do cliente: passa para uma pessoa.

A nota de confiança do log aparece na saída e não entra em nenhuma decisão.

    python3 plano_b.py rodar --conversas conversas-semana.csv
    python3 plano_b.py mostrar --conversas conversas-semana.csv S05
    python3 plano_b.py rodar --conversas conversas-exercicio.csv --precedencia

Só biblioteca padrão, Python 3.9 ou mais novo.
"""
import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
POLITICAS = AQUI.parent / 'dados' / 'politicas' / 'politicas.json'
FAQ = AQUI / 'faq.json'
PERFIS = ('cliente', 'atendimento', 'supervisao', 'financeiro')
COLUNAS = ('id', 'data', 'perfil', 'pedido', 'pede_pessoa', 'pergunta', 'trechos', 'rascunho', 'confianca')
ATENDIMENTO = 'equipe de atendimento'

# Trechos que dizem que uma pessoa faz ou decide alguma coisa, e qual equipe é.
PESSOA_DECIDE = {
    'entregas@1#extravio': ATENDIMENTO,
    'trocas@1#defeito': ATENDIMENTO,
    'pagamentos@1#duplicidade': 'equipe financeira',
}

MOTIVOS = {
    'conflito': 'duas fontes que valem dizem coisas diferentes',
    'busca-vazia': 'nenhum trecho que vale para essa pergunta',
    'modelo-nao-achou': 'o modelo disse que os trechos não respondem',
    'frase-sem-fonte': 'uma frase não cita trecho',
    'fonte-que-nao-valeu': 'uma frase cita um trecho que não valeu',
    'numero-fora-do-trecho': 'um número não está no trecho citado nem na pergunta',
    'pediu-pessoa': 'o cliente pediu uma pessoa',
    'pessoa-decide': 'o trecho usado diz que uma pessoa decide',
    'nao-sei-com-pedido': 'não sabe, e a conversa tem um pedido do cliente',
}
ACOES = {'responder': 'responder', 'nao-sei': 'não sei', 'passar': 'passar'}

MARCA_FONTE = re.compile(r'\[fonte:\s*([^\]]+?)\s*\]')
NAO_ACHEI = '[não achei]'
FRASE = re.compile(r'\s*(.+?[.!?])(?:\s*\[fonte:\s*([^\]]+?)\s*\])?(?=\s|$)', re.S)
NUMERO = re.compile(r'\d+(?:[.,]\d+)*')


class Erro(Exception):
    pass


def ler_json(caminho):
    try:
        return json.loads(caminho.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise Erro(f'não achei {caminho}')
    except json.JSONDecodeError as e:
        raise Erro(f'{caminho.name} não é um JSON válido: {e}')


def ler_base():
    """Políticas do kit e FAQ do site, num dicionário por id. Cada trecho ganha um assunto."""
    base = {}
    for origem in (POLITICAS, FAQ):
        for t in ler_json(origem):
            for campo in ('id', 'documento', 'secao', 'texto', 'inicio', 'perfis', 'status'):
                if campo not in t:
                    raise Erro(f'{origem.name}: o trecho {t.get("id", "(sem id)")} não tem o campo {campo}')
            if t['id'] in base:
                raise Erro(f'{origem.name}: o id {t["id"]} aparece duas vezes')
            t = dict(t)
            t.setdefault('fim', None)
            t.setdefault('assunto', f'{t["documento"]}#{t["secao"]}')
            base[t['id']] = t
    return base


def situacao(trecho, perfil, dia):
    """Diz se o trecho vale para esse perfil nesse dia. 'vale' quando vale."""
    if trecho['status'] != 'aprovado':
        return 'rascunho'
    if perfil not in trecho['perfis']:
        return 'fora do perfil ' + perfil
    if dia < trecho['inicio']:
        return 'ainda não vale em ' + dia
    if trecho['fim'] is not None and dia >= trecho['fim']:
        return 'vencida em ' + trecho['fim']
    return 'vale'


def lista(campo):
    return [x.strip() for x in (campo or '').split('|') if x.strip()]


def ler_conversas(caminho, base):
    try:
        with open(caminho, newline='', encoding='utf-8') as f:
            leitor = csv.DictReader(f)
            faltam = [c for c in COLUNAS if c not in (leitor.fieldnames or [])]
            if faltam:
                raise Erro(f'{caminho}: falta a coluna {", ".join(faltam)}')
            linhas = list(leitor)
    except FileNotFoundError:
        raise Erro(f'não achei o arquivo {caminho}')
    casos, vistos = [], set()
    for n, l in enumerate(linhas, 2):
        cid = (l['id'] or '').strip()
        if not cid:
            raise Erro(f'{caminho}, linha {n}: id vazio')
        if cid in vistos:
            raise Erro(f'{caminho}: o id {cid} aparece duas vezes')
        vistos.add(cid)
        dia = (l['data'] or '').strip()
        try:
            date.fromisoformat(dia)
        except ValueError:
            raise Erro(f'{caminho}, {cid}: data "{dia}" fora do formato AAAA-MM-DD')
        perfil = (l['perfil'] or '').strip()
        if perfil not in PERFIS:
            raise Erro(f'{caminho}, {cid}: perfil "{perfil}" não existe ({", ".join(PERFIS)})')
        pede = (l['pede_pessoa'] or '').strip()
        if pede not in ('sim', 'nao'):
            raise Erro(f'{caminho}, {cid}: pede_pessoa precisa ser sim ou nao, veio "{pede}"')
        pergunta, rascunho = (l['pergunta'] or '').strip(), (l['rascunho'] or '').strip()
        if not pergunta or not rascunho:
            raise Erro(f'{caminho}, {cid}: pergunta ou rascunho vazio')
        trechos = lista(l['trechos'])
        if not trechos:
            raise Erro(f'{caminho}, {cid}: nenhum trecho; o log precisa dizer o que a busca trouxe')
        for t in trechos:
            if t not in base:
                raise Erro(f'{caminho}, {cid}: o trecho {t} não existe nas políticas nem no FAQ')
        try:
            conf = float((l['confianca'] or '').replace(',', '.'))
        except ValueError:
            raise Erro(f'{caminho}, {cid}: confiança "{l["confianca"]}" não é número')
        if not 0 <= conf <= 1:
            raise Erro(f'{caminho}, {cid}: confiança {conf} fora de 0 a 1')
        casos.append({'id': cid, 'data': dia, 'perfil': perfil, 'pedido': (l['pedido'] or '').strip(),
                      'pede_pessoa': pede == 'sim', 'pergunta': pergunta, 'trechos': trechos,
                      'rascunho': rascunho, 'confianca': conf})
    if not casos:
        raise Erro(f'{caminho}: nenhuma conversa')
    return casos


def achar_conflitos(citadas, base, perfil, dia):
    """Para cada assunto das fontes citadas, procura na base inteira outra fonte que vale no mesmo
    dia, para o mesmo perfil, com texto diferente. Não depende de a busca ter trazido as duas."""
    grupos = []
    for assunto in dict.fromkeys(base[t]['assunto'] for t in citadas):
        mesmos = sorted(i for i, t in base.items()
                        if t['assunto'] == assunto and situacao(t, perfil, dia) == 'vale')
        if len({base[i]['texto'] for i in mesmos}) > 1:
            grupos.append({'assunto': assunto, 'ids': mesmos})
    return grupos


def ler_rascunho(texto):
    """Quebra o rascunho em frases, cada uma com a fonte citada (ou None)."""
    nao_achei = texto.lower().startswith(NAO_ACHEI)
    if nao_achei:
        texto = texto[len(NAO_ACHEI):]
    frases = [(m.group(1).strip(), m.group(2)) for m in FRASE.finditer(texto.strip())]
    return {'nao_achei': nao_achei, 'frases': frases}


def numeros(texto):
    """Os números de um texto, como valor: 'R$ 199,00' e '199' dão o mesmo 199."""
    texto = MARCA_FONTE.sub(' ', texto)
    achados = set()
    for n in NUMERO.findall(texto):
        if ',' in n:
            n = n.replace('.', '').replace(',', '.')
        else:
            n = n.replace('.', '')
        achados.add(float(n))
    return achados


def checar_rascunho(rascunho, validos, base, pergunta):
    """Parada 2. Devolve a lista de problemas: (número da frase, motivo, detalhe)."""
    problemas = []
    da_pergunta = numeros(pergunta)
    for n, (frase, fonte) in enumerate(rascunho['frases'], 1):
        if fonte is None:
            if not rascunho['nao_achei']:
                problemas.append((n, 'frase-sem-fonte', frase))
                continue
            fora = numeros(frase) - da_pergunta
            if fora:
                problemas.append((n, 'numero-fora-do-trecho', f'{_num(fora)} numa frase sem fonte'))
            continue
        if fonte not in validos:
            problemas.append((n, 'fonte-que-nao-valeu', fonte))
            continue
        fora = numeros(frase) - numeros(base[fonte]['texto']) - da_pergunta
        if fora:
            problemas.append((n, 'numero-fora-do-trecho', f'{_num(fora)} não está em {fonte}'))
    return problemas


def _num(valores):
    return ', '.join(f'{v:g}'.replace('.', ',') for v in sorted(valores))


def num(x):
    return f'{x:.2f}'.replace('.', ',')


def aplicar_precedencia(conflitos, base, precedencia, validos, descartados, avisos):
    """Com uma regra de precedência, o conflito que ela resolve deixa de parar o fluxo."""
    sobram = []
    for g in conflitos:
        try:
            vencedor = precedencia(list(g['ids']), base)
        except NotImplementedError:
            raise Erro('a função politica_vence_faq ainda não foi escrita (precedencia.py)')
        if vencedor is None:
            sobram.append(g)
            continue
        if vencedor not in g['ids']:
            raise Erro(f'a precedência devolveu {vencedor}, que não está no conflito {", ".join(g["ids"])}')
        for i in g['ids']:
            if i != vencedor:
                if i in validos:
                    validos.remove(i)
                    descartados.append((i, f'perdeu para {vencedor} na precedência'))
                avisos.append(f'corrigir {i}: diz outra coisa sobre {g["assunto"]}; vale {vencedor}')
    return sobram


def decidir(caso, base, precedencia=None):
    """As três paradas. Devolve a ação, os motivos, a parada que decidiu e o que sai para cada lado."""
    r = {'id': caso['id'], 'acao': 'responder', 'parada': '-', 'motivos': [], 'destino': None,
         'descartados': [], 'validos': [], 'conflitos': [], 'problemas': [], 'avisos': [],
         'chamou_modelo': True, 'fontes_usadas': [], 'frases': []}

    # Parada 1: os trechos.
    for t in caso['trechos']:
        s = situacao(base[t], caso['perfil'], caso['data'])
        if s == 'vale':
            r['validos'].append(t)
        else:
            r['descartados'].append((t, s))
    if not r['validos']:
        r.update(acao='nao-sei', parada='1', motivos=['busca-vazia'], chamou_modelo=False)

    # Parada 2: o rascunho do modelo. Primeiro o conflito, depois cada frase.
    if r['chamou_modelo']:
        rascunho = ler_rascunho(caso['rascunho'])
        citadas = list(dict.fromkeys(f for _, f in rascunho['frases'] if f in r['validos']))
        conflitos = achar_conflitos(citadas, base, caso['perfil'], caso['data'])
        if conflitos and precedencia is not None:
            conflitos = aplicar_precedencia(conflitos, base, precedencia, r['validos'], r['descartados'],
                                            r['avisos'])
        r['conflitos'] = conflitos
        if conflitos:
            r.update(acao='passar', parada='2', motivos=['conflito'], destino=ATENDIMENTO)
            for g in conflitos:
                r['avisos'].append(f'as fontes {" e ".join(g["ids"])} dizem coisas diferentes sobre {g["assunto"]}')
        else:
            r['problemas'] = checar_rascunho(rascunho, r['validos'], base, caso['pergunta'])
            if r['problemas']:
                r.update(acao='nao-sei', parada='2', motivos=list(dict.fromkeys(p[1] for p in r['problemas'])))
            else:
                r['frases'] = [f for f, _ in rascunho['frases']]
                r['fontes_usadas'] = list(dict.fromkeys(f for _, f in rascunho['frases'] if f))
                if rascunho['nao_achei']:
                    r.update(acao='nao-sei', parada='2', motivos=['modelo-nao-achou'])

    # Parada 3: quem resolve.
    if r['acao'] != 'passar':
        decide = [t for t in r['fontes_usadas'] if t in PESSOA_DECIDE] if r['acao'] == 'responder' else []
        sem_resposta_com_pedido = r['acao'] == 'nao-sei' and bool(caso['pedido'])
        if caso['pede_pessoa']:
            r['motivos'].append('pediu-pessoa')
        if decide:
            r['motivos'].append('pessoa-decide')
        if sem_resposta_com_pedido:
            r['motivos'].append('nao-sei-com-pedido')
        if caso['pede_pessoa'] or decide or sem_resposta_com_pedido:
            r.update(acao='passar', parada='3', destino=PESSOA_DECIDE[decide[0]] if decide else ATENDIMENTO)
    r['mensagem'] = mensagem(caso, r, base)
    return r


def mensagem(caso, r, base):
    """O que o cliente lê. A resposta só sai quando passou na parada 2."""
    if 'conflito' in r['motivos']:
        partes = ['Achei duas regras diferentes da loja sobre isso e não quero te passar a errada.']
    elif 'busca-vazia' in r['motivos']:
        partes = ['Eu procurei nas políticas da loja e não achei uma regra que responda isso.']
    elif r['problemas']:
        citados = [t for t in dict.fromkeys(f for _, f in ler_rascunho(caso['rascunho'])['frases']) if t in r['validos']]
        achados = citados or r['validos']
        titulos = [f'«{base[t]["titulo"]}»' for t in achados]
        titulos = titulos[0] if len(titulos) == 1 else ', '.join(titulos[:-1]) + ' e ' + titulos[-1]
        texto = 'nesse texto' if len(achados) == 1 else 'nesses textos'
        partes = [f'Eu achei {titulos} nas políticas da loja, mas não consegui confirmar a resposta {texto}.']
    else:
        partes = list(r['frases'])
    if r['acao'] == 'passar':
        quem = r['destino']
        if caso['pedido']:
            partes.append(f'Vou passar o pedido {caso["pedido"]} para a {quem}, com o que eu achei.')
        else:
            partes.append(f'Vou passar a sua conversa para a {quem}, com o que eu achei.')
    elif r['acao'] == 'nao-sei':
        partes.append('Se quiser, eu passo a sua pergunta para uma pessoa do atendimento.')
    return ' '.join(partes)


def mostrar(caso, base, precedencia=None):
    r = decidir(caso, base, precedencia)
    print(f'{caso["id"]}  {caso["perfil"]}, {caso["data"]}' + (f', pedido {caso["pedido"]}' if caso['pedido'] else '')
          + (', pediu uma pessoa' if caso['pede_pessoa'] else ''))
    print(f'pergunta: {caso["pergunta"]}')
    print('trechos que a busca trouxe:')
    desc = dict(r['descartados'])
    em_conflito = {i for g in r['conflitos'] for i in g['ids']}
    for i, t in enumerate(caso['trechos'], 1):
        marca = f'  [NÃO VALE: {desc[t]}]' if t in desc else ('  [CONFLITO]' if t in em_conflito else '')
        print(f'  {i}. {t}{marca}')
        print(f'     {base[t]["texto"]}')
    for g in r['conflitos']:
        for i in g['ids']:
            if i not in caso['trechos']:
                print(f'  +  {i}  [CONFLITO: a busca não trouxe, o plano B achou pelo assunto {g["assunto"]}]')
                print(f'     {base[i]["texto"]}')
    if r['chamou_modelo']:
        print(f'rascunho do modelo (confiança {num(caso["confianca"])}):')
    else:
        print(f'rascunho do log (confiança {num(caso["confianca"])}; com o plano B, o modelo nem seria chamado):')
    print(f'  {caso["rascunho"]}')
    for n, motivo, detalhe in r['problemas']:
        print(f'  frase {n}: {MOTIVOS[motivo]} ({detalhe})')
    onde = 'passou pelas três paradas' if r['parada'] == '-' else f'parada {r["parada"]}'
    print(f'{onde}: {ACOES[r["acao"]]}' + (f', para a {r["destino"]}' if r['destino'] else ''))
    for m in r['motivos']:
        print(f'  motivo: {m}, {MOTIVOS[m]}')
    print('mensagem ao cliente:')
    print(f'  {r["mensagem"]}')
    if r['acao'] == 'passar':
        print('pacote para a pessoa:')
        print(f'  trechos que valeram: {", ".join(r["validos"]) or "nenhum"}')
        if r['descartados']:
            print('  trechos tirados: ' + '; '.join(f'{t} ({s})' for t, s in r['descartados']))
        for g in r['conflitos']:
            print(f'  conflito sobre {g["assunto"]}: {" × ".join(g["ids"])}')
        if r['problemas'] or r['conflitos']:
            print('  rascunho não enviado: ' + caso['rascunho'])
    for a in r['avisos']:
        print(f'aviso para quem cuida das políticas: {a}')


def rodar(casos, base, precedencia=None):
    rs = [decidir(c, base, precedencia) for c in casos]
    print(f'{"id":<4} {"parada":<6} {"ação":<9} {"motivo":<44} destino')
    for r in rs:
        print(f'{r["id"]:<4} {r["parada"]:<6} {ACOES[r["acao"]]:<9} {" + ".join(r["motivos"]) or "-":<44} '
              f'{r["destino"] or "-"}')
    print()
    print(f'ações ({len(rs)} conversas)')
    for a in ACOES:
        ids = [r['id'] for r in rs if r['acao'] == a]
        print(f'  {ACOES[a]:<10} {len(ids):>2}   {" ".join(ids)}')
    print()
    print('motivos (uma conversa pode ter mais de um)')
    for m in MOTIVOS:
        ids = [r['id'] for r in rs if m in r['motivos']]
        if ids:
            print(f'  {m:<22} {len(ids):>2}   {" ".join(ids)}')
    print()
    print('o modelo nem seria chamado em ' + str(sum(1 for r in rs if not r['chamou_modelo'])) + f' de {len(rs)}')
    avisos = [(r['id'], a) for r in rs for a in r['avisos']]
    if avisos:
        print()
        print('avisos para quem cuida das políticas')
        for i, a in avisos:
            print(f'  {i}: {a}')
    print()
    print('confiança do log por ação (não entrou em nenhuma decisão)')
    conf = {c['id']: c['confianca'] for c in casos}
    for a in ACOES:
        v = [conf[r['id']] for r in rs if r['acao'] == a]
        if v:
            print(f'  {ACOES[a]:<10} de {num(min(v))} a {num(max(v))}')


def carregar_precedencia():
    sys.path.insert(0, str(AQUI))
    try:
        from precedencia import politica_vence_faq
    except ImportError as e:
        raise Erro(f'não consegui ler precedencia.py: {e}')
    return politica_vence_faq


def main(argv=None):
    p = argparse.ArgumentParser(description='Plano B: responder, dizer que não sabe ou passar para uma pessoa.')
    sub = p.add_subparsers(dest='comando')
    for nome, ajuda in (('rodar', 'roda o plano B em todas as conversas'),
                        ('mostrar', 'mostra uma conversa, parada por parada')):
        s = sub.add_parser(nome, help=ajuda)
        s.add_argument('--conversas', required=True)
        s.add_argument('--precedencia', action='store_true',
                       help='usa a regra de precedencia.py para resolver conflitos')
        if nome == 'mostrar':
            s.add_argument('id')
    a = p.parse_args(argv)
    if not a.comando:
        p.print_help()
        return 2
    try:
        base = ler_base()
        casos = ler_conversas(a.conversas, base)
        prec = carregar_precedencia() if a.precedencia else None
        if a.comando == 'rodar':
            rodar(casos, base, prec)
        else:
            achados = [c for c in casos if c['id'] == a.id]
            if not achados:
                raise Erro(f'o id {a.id} não está em {a.conversas}')
            mostrar(achados[0], base, prec)
    except Erro as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
