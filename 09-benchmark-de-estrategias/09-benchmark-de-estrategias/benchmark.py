"""Compara estratégias no mesmo conjunto: qualidade por tipo, tempo e custo, e aplica a regra.

Busca (cada linha do registro é uma pergunta numa estratégia):
    python3 benchmark.py busca --conjunto conjunto-avaliacao.csv \
        --registro registro-bm25.csv --registro registro-fornecedor.csv --regra regra-busca.json

Agente (cada linha do registro é uma tarefa numa versão do agente):
    python3 benchmark.py agente --conjunto tarefas-agente.csv \
        --registro registro-agente.csv --regra regra-agente.json

O programa para com código 2 quando as estratégias não rodaram exatamente as mesmas
perguntas do conjunto. Com --descartar-fora-do-conjunto, ele tira as linhas de perguntas
que não estão no conjunto, diz quais tirou e segue. Pergunta do conjunto que faltou no
registro sempre para o programa.

Tempo: p50 e p95 pelo método do posto mais próximo (o valor na posição ceil(p * n) da
lista ordenada). Com 16 perguntas, o p95 é a pergunta mais lenta.

Só usa a biblioteca padrão do Python 3.9 ou mais novo.
"""
import argparse
import csv
import json
import math
import sys
from datetime import date
from pathlib import Path

PASTA = Path(__file__).resolve().parent
POLITICAS = PASTA.parent / 'dados' / 'politicas' / 'politicas.json'
PRECOS = PASTA / 'precos.json'


class ErroEntrada(ValueError):
    pass


# ---------- leitura ----------

def ler_csv(caminho, colunas):
    try:
        with open(caminho, encoding='utf-8', newline='') as f:
            linhas = list(csv.DictReader(f))
    except FileNotFoundError:
        raise ErroEntrada(f'arquivo não encontrado: {caminho}')
    if not linhas:
        raise ErroEntrada(f'{caminho} não tem nenhuma linha')
    faltando = set(colunas) - set(linhas[0])
    if faltando:
        raise ErroEntrada(f'{caminho}: faltam colunas {", ".join(sorted(faltando))}')
    return [{k: (v or '').strip() for k, v in linha.items() if k is not None} for linha in linhas]


def ler_json(caminho):
    try:
        with open(caminho, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise ErroEntrada(f'arquivo não encontrado: {caminho}')
    except json.JSONDecodeError as e:
        raise ErroEntrada(f'{caminho} não é um JSON válido: {e}')


def ler_conjunto(caminho):
    linhas = ler_csv(caminho, ['id', 'tipo', 'pergunta'])
    vistos = set()
    for linha in linhas:
        if not linha['id'] or not linha['tipo'] or not linha['pergunta']:
            raise ErroEntrada(f'conjunto: linha sem id, tipo ou pergunta: {linha}')
        if linha['id'] in vistos:
            raise ErroEntrada(f'conjunto: id repetido {linha["id"]}')
        vistos.add(linha['id'])
    return linhas


def numero(texto, campo, onde, inteiro=False):
    try:
        valor = int(texto) if inteiro else float(texto)
    except ValueError:
        raise ErroEntrada(f'{onde}: {campo} inválido: {texto!r}')
    if valor < 0 or (not inteiro and not math.isfinite(valor)):
        raise ErroEntrada(f'{onde}: {campo} não pode ser negativo: {texto!r}')
    return valor


def juntar_registros(caminhos, colunas, chave, ids, descartar):
    """Junta os registros e exige que cada estratégia tenha rodado todo o conjunto, uma vez."""
    por_estrategia, ordem, descartadas = {}, [], []
    for caminho in caminhos:
        for linha in ler_csv(caminho, colunas):
            nome, qid = linha[chave], linha['id']
            if not nome or not qid:
                raise ErroEntrada(f'{caminho}: linha sem {chave} ou sem id: {linha}')
            if qid not in ids:
                if descartar:
                    descartadas.append(f'{nome} {qid}')
                    continue
                raise ErroEntrada(f'{nome}: {qid} não está no conjunto. Compare só as mesmas perguntas '
                                  f'(ou rode com --descartar-fora-do-conjunto e diga isso na decisão)')
            if nome not in por_estrategia:
                por_estrategia[nome] = {}
                ordem.append(nome)
            if qid in por_estrategia[nome]:
                raise ErroEntrada(f'{nome}: {qid} aparece duas vezes no registro')
            por_estrategia[nome][qid] = linha
    for nome in ordem:
        faltando = [i for i in ids if i not in por_estrategia[nome]]
        if faltando:
            raise ErroEntrada(f'{nome}: faltam {len(faltando)} do conjunto ({", ".join(faltando)}). '
                              f'Sem as mesmas perguntas, a comparação não vale')
    return ordem, por_estrategia, descartadas


def ler_politicas(regra):
    """Ids que o perfil pode ler na data da regra (aprovados e vigentes) e todos os ids."""
    trechos = ler_json(POLITICAS)
    try:
        dia = date.fromisoformat(regra['data'])
    except (KeyError, ValueError):
        raise ErroEntrada('regra: campo data ausente ou inválido (use AAAA-MM-DD)')
    perfil = regra.get('perfil', '')
    vale = set()
    for t in trechos:
        inicio = date.fromisoformat(t['inicio'])
        fim = date.fromisoformat(t['fim']) if t['fim'] else None
        if (t['status'] == 'aprovado' and perfil in t['perfis']
                and inicio <= dia and (fim is None or dia < fim)):
            vale.add(t['id'])
    if not vale:
        raise ErroEntrada(f'regra: nenhum trecho vale para o perfil {perfil!r} em {dia}')
    return vale, {t['id'] for t in trechos}


# ---------- contas ----------

def posto(valores, p):
    """Percentil pelo posto mais próximo: o valor na posição ceil(p * n) da lista ordenada."""
    ordenados = sorted(valores)
    return ordenados[max(1, math.ceil(p * len(ordenados))) - 1]


def tipos_em_ordem(conjunto):
    return list(dict.fromkeys(q['tipo'] for q in conjunto))


def exigir_tipos(regra, campo, tipos):
    nomes = regra.get(campo, [])
    if not isinstance(nomes, list):
        raise ErroEntrada(f'regra: {campo} precisa ser uma lista de tipos')
    fora = [t for t in nomes if t not in tipos]
    if fora:
        raise ErroEntrada(f'regra: {campo} cita tipos que não estão no conjunto: {", ".join(fora)}')
    return nomes


def exigir(dic, campo, onde):
    if campo not in dic:
        raise ErroEntrada(f'{onde}: falta o campo {campo}')
    return dic[campo]


def reais(valor):
    return f'R$ {valor:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def marca(ok):
    return 'ok   ' if ok else 'FALHA'


# ---------- busca ----------

def medir_busca(conjunto, linhas, k, precos, vale, todos):
    emb = exigir(precos, 'embedding_por_milhao_tokens', 'precos.json')
    rer = exigir(precos, 'reranker_por_mil_pares', 'precos.json')
    por_tipo, tempos, custo = {}, [], 0.0
    for q in conjunto:
        linha = linhas[q['id']]
        onde = f'{linha["estrategia"]} {q["id"]}'
        ranking = [r for r in linha['ranking'].split('|') if r]
        desconhecidos = [r for r in ranking if r not in todos]
        if desconhecidos:
            raise ErroEntrada(f'{onde}: trecho que não existe nas políticas: {", ".join(desconhecidos)}')
        fora = [r for r in ranking if r not in vale]
        if fora:
            raise ErroEntrada(f'{onde}: trouxe trecho que o perfil não pode ler nessa data '
                              f'({", ".join(fora)}). O filtro vale para toda estratégia')
        if len(ranking) != len(set(ranking)):
            raise ErroEntrada(f'{onde}: trecho repetido no ranking')
        tempos.append(numero(linha['tempo_ms'], 'tempo_ms', onde))
        tokens = numero(linha['tokens_embedding'], 'tokens_embedding', onde, inteiro=True)
        pares = numero(linha['pares_reranker'], 'pares_reranker', onde, inteiro=True)
        custo += tokens / 1e6 * emb + pares / 1000 * rer
        esperados = [e for e in q.get('esperado', '').split('|') if e]
        topo = ranking[:k]
        d = por_tipo.setdefault(q['tipo'], {'com': 0, 'achou': 0, 'primeiro': 0, 'rr': 0.0,
                                            'sem': 0, 'vazias': 0})
        if esperados:
            pos = next((i for i, r in enumerate(topo, 1) if r in esperados), None)
            d['com'] += 1
            d['achou'] += 1 if pos else 0
            d['primeiro'] += 1 if pos == 1 else 0
            d['rr'] += 1 / pos if pos else 0.0
        else:
            d['sem'] += 1
            d['vazias'] += 0 if topo else 1
    n = len(conjunto)
    return {'tipos': por_tipo, 'p50': posto(tempos, 0.5), 'p95': posto(tempos, 0.95),
            'custo_mil': custo / n * 1000}


def celula_busca(d):
    if d['com']:
        return f'{d["achou"]}/{d["com"]}  {d["primeiro"]}/{d["com"]}  {d["rr"] / d["com"]:.2f}'
    return f'vazias {d["vazias"]}/{d["sem"]}'


def soma(m, tipos, campo):
    return sum(m['tipos'][t][campo] for t in tipos)


def mrr(m, tipos):
    com = soma(m, tipos, 'com')
    return soma(m, tipos, 'rr') / com if com else 0.0


def rodar_busca(args):
    regra = ler_json(args.regra)
    precos = ler_json(args.precos)
    k = exigir(regra, 'k', 'regra')
    if not isinstance(k, int) or k < 1:
        raise ErroEntrada('regra: k precisa ser um inteiro, 1 ou mais')
    vale, todos = ler_politicas(regra)
    conjunto = ler_conjunto(args.conjunto)
    for q in conjunto:
        q.setdefault('esperado', '')
        fora = [e for e in q['esperado'].split('|') if e and e not in vale]
        if fora:
            raise ErroEntrada(f'conjunto {q["id"]}: esperado fora do filtro ou inexistente: {", ".join(fora)}')
    ids = [q['id'] for q in conjunto]
    tipos = tipos_em_ordem(conjunto)
    ordem, registros, descartadas = juntar_registros(
        args.registro, ['estrategia', 'id', 'ranking', 'tempo_ms', 'tokens_embedding', 'pares_reranker'],
        'estrategia', ids, args.descartar_fora_do_conjunto)
    base = exigir(regra, 'base', 'regra')
    if base not in registros:
        raise ErroEntrada(f'regra: a base {base!r} não está nos registros ({", ".join(ordem)})')
    anteriores = regra.get('etapa_anterior', {})
    for nova, antiga in anteriores.items():
        if nova not in registros or antiga not in registros:
            raise ErroEntrada(f'regra: etapa_anterior cita estratégia sem registro: {nova} -> {antiga}')
    nao_cai = exigir_tipos(regra, 'nao_pode_cair', tipos)
    sobe = exigir_tipos(regra, 'precisa_subir', tipos)
    p95_max = exigir(regra, 'p95_max_ms', 'regra')
    teto = exigir(regra, 'custo_mes_max', 'regra')
    volume = exigir(regra, 'volume_mes', 'regra')

    medidas = {nome: medir_busca(conjunto, registros[nome], k, precos, vale, todos) for nome in ordem}
    contagem = ', '.join(f'{sum(1 for q in conjunto if q["tipo"] == t)} {t}' for t in tipos)
    print(f'conjunto: {len(conjunto)} perguntas ({contagem})')
    print(f'filtro: perfil {regra["perfil"]}, data {regra["data"]}, {len(vale)} trechos aprovados e vigentes')
    for item in descartadas:
        print(f'descartada (fora do conjunto): {item}')
    print(f'estratégias: {", ".join(ordem)} ({len(conjunto)} perguntas cada)')
    print()
    print(f'qualidade com k = {k}: achou entre os {k} / em 1º / MRR')
    largura = max(18, *(len(n) + 2 for n in ordem))
    print(f'{"tipo":<14}' + ''.join(f'{n:<{largura}}' for n in ordem))
    for t in tipos:
        print(f'{t:<14}' + ''.join(f'{celula_busca(medidas[n]["tipos"][t]):<{largura}}' for n in ordem))
    print()
    print(f'{"tempo e custo":<14}' + ''.join(f'{n:<{largura}}' for n in ordem))
    print(f'{"p50 (ms)":<14}' + ''.join(f'{medidas[n]["p50"]:<{largura}.1f}' for n in ordem))
    print(f'{"p95 (ms)":<14}' + ''.join(f'{medidas[n]["p95"]:<{largura}.1f}' for n in ordem))
    print(f'{"R$/mil":<14}' + ''.join(f'{medidas[n]["custo_mil"]:<{largura}.4f}' for n in ordem))
    print(f'{"R$/mês":<14}' + ''.join(f'{medidas[n]["custo_mil"] * volume / 1000:<{largura}.2f}'
                                         for n in ordem))
    print()
    print(f'regra escrita antes do teste (base: {base}; {volume} perguntas por mês)')
    b = medidas[base]
    for nome in ordem:
        if nome == base:
            continue
        m = medidas[nome]
        conds = []
        for t in nao_cai:
            ok = m['tipos'][t]['achou'] >= b['tipos'][t]['achou'] and mrr(m, [t]) >= mrr(b, [t]) - 1e-9
            conds.append((ok, f'{t} não cai: achou {m["tipos"][t]["achou"]} contra {b["tipos"][t]["achou"]}, '
                              f'MRR {mrr(m, [t]):.2f} contra {mrr(b, [t]):.2f}'))
        for t in sobe:
            a, ab = m['tipos'][t]['achou'], b['tipos'][t]['achou']
            conds.append((a > ab, f'{t} sobe: achou {a} contra {ab}'))
        if nome in anteriores:
            ant = medidas[anteriores[nome]]
            com = [t for t in tipos if m['tipos'][t]['com']]
            p, pa = soma(m, com, 'primeiro'), soma(ant, com, 'primeiro')
            conds.append((p > pa, f'em 1º sobe contra {anteriores[nome]}: {p} contra {pa}'))
        conds.append((m['p95'] <= p95_max, f'p95 {m["p95"]:.1f} ms, teto {p95_max} ms'))
        mes = m['custo_mil'] * volume / 1000
        conds.append((mes <= teto, f'custo {reais(mes)} por mês, teto {reais(teto)}'))
        print(nome)
        for ok, texto in conds:
            print(f'  {marca(ok)} {texto}')
        print(f'  {"passa" if all(ok for ok, _ in conds) else "não passa"}')
    return 0


# ---------- agente ----------

def medir_agente(conjunto, linhas, precos):
    modelos = exigir(precos, 'modelos', 'precos.json')
    por_tipo, tempos = {}, []
    for q in conjunto:
        linha = linhas[q['id']]
        onde = f'{linha["versao"]} {q["id"]}'
        if linha['aprovada'] not in ('sim', 'nao'):
            raise ErroEntrada(f'{onde}: aprovada precisa ser sim ou nao, veio {linha["aprovada"]!r}')
        modelo = linha['modelo']
        if modelo not in modelos:
            raise ErroEntrada(f'{onde}: modelo {modelo!r} sem preço em precos.json')
        preco = modelos[modelo]
        ent = numero(linha['tokens_entrada'], 'tokens_entrada', onde, inteiro=True)
        sai = numero(linha['tokens_saida'], 'tokens_saida', onde, inteiro=True)
        passos = numero(linha['passos'], 'passos', onde, inteiro=True)
        if passos < 1:
            raise ErroEntrada(f'{onde}: passos precisa ser 1 ou mais')
        tempos.append(numero(linha['tempo_ms'], 'tempo_ms', onde))
        custo = ent / 1e6 * exigir(preco, 'entrada_por_milhao', modelo) \
            + sai / 1e6 * exigir(preco, 'saida_por_milhao', modelo)
        d = por_tipo.setdefault(q['tipo'], {'n': 0, 'ok': 0, 'passos': 0, 'custo': 0.0})
        d['n'] += 1
        d['ok'] += 1 if linha['aprovada'] == 'sim' else 0
        d['passos'] += passos
        d['custo'] += custo
    return {'tipos': por_tipo, 'p50': posto(tempos, 0.5), 'p95': posto(tempos, 0.95)}


def custo_mil(d):
    return d['custo'] / d['n'] * 1000


def rodar_agente(args):
    regra = ler_json(args.regra)
    precos = ler_json(args.precos)
    conjunto = ler_conjunto(args.conjunto)
    ids = [q['id'] for q in conjunto]
    tipos = tipos_em_ordem(conjunto)
    ordem, registros, descartadas = juntar_registros(
        args.registro, ['versao', 'id', 'modelo', 'aprovada', 'passos', 'tokens_entrada', 'tokens_saida',
                        'tempo_ms'], 'versao', ids, args.descartar_fora_do_conjunto)
    base = exigir(regra, 'base', 'regra')
    if base not in registros:
        raise ErroEntrada(f'regra: a base {base!r} não está nos registros ({", ".join(ordem)})')
    mistura = exigir(regra, 'mistura_mes', 'regra')
    if set(mistura) != set(tipos):
        raise ErroEntrada(f'regra: mistura_mes precisa ter exatamente os tipos do conjunto ({", ".join(tipos)})')
    if abs(sum(mistura.values()) - 1) > 1e-6 or any(v < 0 for v in mistura.values()):
        raise ErroEntrada('regra: as partes de mistura_mes precisam somar 1')
    volume = exigir(regra, 'volume_mes', 'regra')
    p95_max = exigir(regra, 'p95_max_ms', 'regra')
    alta = regra.get('custo_sobe_no_maximo')
    nao_cai = exigir_tipos(regra, 'nao_pode_cair', tipos)

    medidas = {nome: medir_agente(conjunto, registros[nome], precos) for nome in ordem}
    contagem = ', '.join(f'{sum(1 for q in conjunto if q["tipo"] == t)} {t}' for t in tipos)
    print(f'conjunto: {len(conjunto)} tarefas ({contagem})')
    for item in descartadas:
        print(f'descartada (fora do conjunto): {item}')
    print(f'versões: {", ".join(ordem)} ({len(conjunto)} tarefas cada)')
    print()
    print('por tipo: aprovadas / passos por tarefa / R$ por mil tarefas')
    largura = max(22, *(len(n) + 2 for n in ordem))
    print(f'{"tipo":<14}' + ''.join(f'{n:<{largura}}' for n in ordem))
    for t in tipos:
        cel = []
        for n in ordem:
            d = medidas[n]['tipos'][t]
            cel.append(f'{d["ok"]}/{d["n"]}  {d["passos"] / d["n"]:.2f}  {custo_mil(d):.2f}')
        print(f'{t:<14}' + ''.join(f'{c:<{largura}}' for c in cel))
    total = {n: sum(medidas[n]['tipos'][t]['ok'] for t in tipos) for n in ordem}
    print(f'{"total":<14}' + ''.join(f'{f"{total[n]}/{len(conjunto)}":<{largura}}' for n in ordem))
    print(f'{"p50 (ms)":<14}' + ''.join(f'{medidas[n]["p50"]:<{largura}.0f}' for n in ordem))
    print(f'{"p95 (ms)":<14}' + ''.join(f'{medidas[n]["p95"]:<{largura}.0f}' for n in ordem))
    no_mes = {n: sum(mistura[t] * custo_mil(medidas[n]['tipos'][t]) for t in tipos) for n in ordem}
    print(f'{"R$/mil, mês":<14}' + ''.join(f'{no_mes[n]:<{largura}.2f}' for n in ordem))
    print()

    mix = ', '.join(f'{round(mistura[t] * 100)}% {t}' for t in tipos)
    print('por tipo, a versão que mais aprova (no empate, a mais barata):')
    escolha = {}
    for t in tipos:
        escolha[t] = min(ordem, key=lambda n: (-medidas[n]['tipos'][t]['ok'],
                                               custo_mil(medidas[n]['tipos'][t]), ordem.index(n)))
        print(f'  {t:<14} {escolha[t]}')
    print(f'custo no mês ({volume} tarefas; {mix}):')
    for n in ordem:
        print(f'  só {n:<20} {reais(no_mes[n] * volume / 1000)}')
    roteado = sum(mistura[t] * custo_mil(medidas[escolha[t]]['tipos'][t]) for t in tipos)
    print(f'  {"por tipo":<23} {reais(roteado * volume / 1000)}')
    print()
    print(f'regra escrita antes do teste (base: {base})')
    b = medidas[base]
    for nome in ordem:
        if nome == base:
            continue
        m = medidas[nome]
        conds = []
        for t in nao_cai:
            conds.append((m['tipos'][t]['ok'] >= b['tipos'][t]['ok'],
                          f'{t} não cai: {m["tipos"][t]["ok"]} contra {b["tipos"][t]["ok"]}'))
        conds.append((m['p95'] <= p95_max, f'p95 {m["p95"]:.0f} ms, teto {p95_max} ms'))
        if alta is not None:
            var = no_mes[nome] / no_mes[base] - 1 if no_mes[base] else 0.0
            conds.append((var <= alta + 1e-9, f'custo por mil tarefas no mês {var * 100:+.1f}%, '
                                              f'teto {alta * 100:+.0f}%'))
        print(nome)
        for ok, texto in conds:
            print(f'  {marca(ok)} {texto}')
        print(f'  {"passa" if all(ok for ok, _ in conds) else "não passa"}')
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description='Compara estratégias no mesmo conjunto.')
    sub = p.add_subparsers(dest='modo')
    for modo in ('busca', 'agente'):
        s = sub.add_parser(modo)
        s.add_argument('--conjunto', required=True)
        s.add_argument('--registro', action='append', required=True,
                       help='CSV do registro; repita para juntar mais de um')
        s.add_argument('--regra', required=True)
        s.add_argument('--precos', default=str(PRECOS))
        s.add_argument('--descartar-fora-do-conjunto', action='store_true')
    args = p.parse_args(argv)
    if not args.modo:
        p.print_help()
        return 2
    try:
        return rodar_busca(args) if args.modo == 'busca' else rodar_agente(args)
    except ErroEntrada as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
