"""Monta e trava o conjunto de referência do assistente da Loja Exemplo.

Três comandos:
    python3 conjunto.py checar conjunto-exemplo.csv
    python3 conjunto.py separar conjunto-exemplo.csv --pasta saida-exemplo
    python3 conjunto.py trava saida-exemplo

checar   lê o CSV e aponta cada linha que não serve como pergunta de teste:
         trecho esperado que não existe, que é rascunho, que não vale na data ou que
         o perfil não lê; número da resposta que não está no trecho; pergunta sem
         resposta com trecho preenchido; a mesma pergunta em dois grupos.
separar  divide os grupos em desenvolvimento e avaliação. Quem decide o lado é o
         sha256 do nome do grupo, dentro de cada tipo (nas sem resposta, dentro de
         cada motivo). Um grupo nunca fica dividido.
         Grava dev.csv, avaliacao.csv e ficha.json numa pasta nova.
trava    recalcula os sha256 da ficha e diz se a avaliação, o desenvolvimento ou as
         políticas mudaram depois da separação.

Colunas do CSV: id, grupo, pergunta, perfil, data, tipo, esperados, resposta, motivo.
Vários trechos esperados vão separados por "|".

Só usa a biblioteca padrão do Python 3.9 ou mais novo.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

PASTA = Path(__file__).resolve().parent
POLITICAS = PASTA.parent / 'dados' / 'politicas' / 'politicas.json'
COLUNAS = ['id', 'grupo', 'pergunta', 'perfil', 'data', 'tipo', 'esperados', 'resposta', 'motivo']
PERFIS = ('cliente', 'atendimento', 'supervisao', 'financeiro')
TIPOS = ('termo exato', 'paráfrase', 'número', 'data', 'duas partes', 'sem resposta')
MOTIVOS = ('fora das políticas', 'outro perfil')
FRACAO = 0.4
PARECIDAS = 0.6

# As mesmas palavras de parada da busca da aula 04.
PARADAS = {
    'a', 'o', 'as', 'os', 'um', 'uma', 'de', 'da', 'do', 'das', 'dos', 'e', 'em', 'no', 'na',
    'nos', 'nas', 'ao', 'aos', 'para', 'pra', 'por', 'com', 'que', 'se', 'eu', 'meu', 'minha',
    'me', 'voce', 'voces', 'qual', 'quais', 'quanto', 'quantos', 'quantas', 'como', 'posso',
    'pode', 'ate', 'mais', 'tem', 'ter', 'sao', 'foi', 'esta', 'isso', 'ele', 'ela', 'mas',
    'nao', 'ou', 'sem', 'depois', 'quando', 'onde', 'dar', 'vai', 'sobre',
}


class ErroEntrada(ValueError):
    pass


def sem_acento(texto):
    return unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii').lower()


def normalizar(pergunta):
    """Texto para achar a mesma pergunta escrita de novo: sem acento, sem pontuação, minúsculas."""
    return ' '.join(re.findall(r'[a-z0-9]+', sem_acento(pergunta)))


def termos(texto):
    saida = set()
    for p in re.findall(r'[a-z0-9]+', sem_acento(texto)):
        if p in PARADAS or (p.isalpha() and len(p) < 2):
            continue
        saida.add(p)
    return saida


def numeros(texto):
    return re.findall(r'\d+(?:[.,]\d+)*', texto)


def sha256(caminho):
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def carregar_politicas(caminho):
    try:
        with open(caminho, encoding='utf-8') as f:
            return {t['id']: t for t in json.load(f)}
    except FileNotFoundError:
        raise ErroEntrada(f'arquivo de políticas não encontrado: {caminho}')
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ErroEntrada(f'arquivo de políticas quebrado: {caminho} ({e})')


def ler_csv(caminho):
    try:
        with open(caminho, encoding='utf-8', newline='') as f:
            leitor = csv.DictReader(f)
            linhas = list(leitor)
            campos = leitor.fieldnames or []
    except FileNotFoundError:
        raise ErroEntrada(f'arquivo não encontrado: {caminho}')
    faltando = [c for c in COLUNAS if c not in campos]
    if faltando:
        raise ErroEntrada(f'faltam colunas no CSV: {", ".join(faltando)}')
    if not linhas:
        raise ErroEntrada('o CSV não tem nenhuma pergunta')
    for linha in linhas:
        for c in COLUNAS:
            linha[c] = (linha.get(c) or '').strip()
    return linhas


def esperados_de(linha):
    return [e.strip() for e in linha['esperados'].split('|') if e.strip()]


def problemas_da_linha(linha, politicas):
    """Lista de textos, um por problema. Lista vazia quando a linha serve."""
    p = []
    if not linha['grupo']:
        p.append('grupo vazio')
    if not linha['pergunta']:
        p.append('pergunta vazia')
    if linha['perfil'] not in PERFIS:
        p.append(f'perfil desconhecido {linha["perfil"]!r} (use {", ".join(PERFIS)})')
    dia = None
    try:
        dia = date.fromisoformat(linha['data'])
    except ValueError:
        p.append(f'data inválida {linha["data"]!r} (use AAAA-MM-DD)')
    if not linha['tipo']:
        p.append('tipo vazio')
        return p
    if linha['tipo'] not in TIPOS:
        p.append(f'tipo desconhecido {linha["tipo"]!r} (use {", ".join(TIPOS)})')
    esperados = esperados_de(linha)
    if linha['tipo'] == 'sem resposta':
        if esperados:
            p.append('pergunta sem resposta não pode ter trecho esperado')
        if linha['resposta']:
            p.append('pergunta sem resposta não pode ter resposta esperada')
        if linha['motivo'] not in MOTIVOS:
            p.append(f'pergunta sem resposta precisa de motivo ({" ou ".join(MOTIVOS)})')
        return p
    if linha['motivo']:
        p.append('só pergunta sem resposta tem motivo')
    if not esperados:
        p.append('pergunta com resposta precisa de pelo menos um trecho esperado')
    if not linha['resposta']:
        p.append('pergunta com resposta precisa da resposta esperada')
    if linha['tipo'] == 'duas partes' and len(esperados) < 2:
        p.append('pergunta de duas partes precisa de dois trechos esperados')
    textos = []
    for e in esperados:
        t = politicas.get(e)
        if t is None:
            p.append(f'trecho {e} não existe nas políticas')
            continue
        textos.append(t['titulo'] + ' ' + t['texto'])
        if t['status'] != 'aprovado':
            p.append(f'trecho {e} é {t["status"]}: o assistente não usa')
        if dia is not None:
            inicio = date.fromisoformat(t['inicio'])
            fim = date.fromisoformat(t['fim']) if t['fim'] else None
            if dia < inicio or (fim is not None and dia >= fim):
                ate = f'até {fim.isoformat()} (sem incluir)' if fim else 'sem fim'
                p.append(f'trecho {e} não vale em {dia.isoformat()} (vale de {inicio.isoformat()} {ate})')
        if linha['perfil'] in PERFIS and linha['perfil'] not in t['perfis']:
            p.append(f'perfil {linha["perfil"]} não lê o trecho {e}')
    if textos:
        juntos = ' '.join(textos)
        for n in numeros(linha['resposta']):
            if not re.search(r'(?<![\d.,])' + re.escape(n) + r'(?![\d]|[.,]\d)', juntos):
                p.append(f'o número {n} da resposta não está nos trechos esperados')
    return p


def checar(linhas, politicas, limiar=PARECIDAS):
    """(problemas, atencoes). problemas: lista de (id, texto). atencoes: pares parecidos em grupos diferentes."""
    problemas = []
    vistos = {}
    for linha in linhas:
        if not linha['id']:
            problemas.append(('?', f'linha sem id: pergunta {linha["pergunta"]!r}'))
            continue
        if linha['id'] in vistos:
            problemas.append((linha['id'], 'id repetido'))
        vistos[linha['id']] = linha
        for texto in problemas_da_linha(linha, politicas):
            problemas.append((linha['id'], texto))
    # A mesma pergunta duas vezes.
    por_texto = {}
    for linha in linhas:
        if linha['pergunta'] and linha['id']:
            por_texto.setdefault(normalizar(linha['pergunta']), []).append(linha)
    for mesmas in por_texto.values():
        grupos = sorted({m['grupo'] for m in mesmas})
        if len(grupos) > 1:
            ids = ', '.join(m['id'] for m in mesmas)
            problemas.append((mesmas[0]['id'], f'a mesma pergunta está em grupos diferentes ({ids}: '
                                               f'{", ".join(grupos)}): ela vazaria entre os lados'))
        chaves = {}
        for m in mesmas:
            chave = (m['perfil'], m['data'])
            if chave in chaves:
                problemas.append((m['id'], f'repete {chaves[chave]} (mesma pergunta, perfil e data)'))
            chaves[chave] = m['id']
    # Perguntas parecidas em grupos diferentes: aviso, a pessoa decide.
    atencoes = []
    validas = [l for l in linhas if l['id'] and l['pergunta']]
    for i, a in enumerate(validas):
        ta = termos(a['pergunta'])
        for b in validas[i + 1:]:
            if a['grupo'] == b['grupo'] or normalizar(a['pergunta']) == normalizar(b['pergunta']):
                continue
            tb = termos(b['pergunta'])
            if not ta or not tb:
                continue
            j = len(ta & tb) / len(ta | tb)
            if j >= limiar:
                atencoes.append((a['id'], b['id'], j))
    return problemas, atencoes


def mostrar_checagem(linhas, problemas, atencoes):
    grupos = {l['grupo'] for l in linhas if l['grupo']}
    print(f'{len(linhas)} perguntas, {len(grupos)} grupos, {len(problemas)} problema(s)')
    for pid, texto in problemas:
        print(f'  {pid:<5} {texto}')
    if not problemas:
        print()
        print(f'{"tipo":<14} {"perguntas":>9}')
        for t in TIPOS:
            n = sum(1 for l in linhas if l['tipo'] == t)
            if n:
                print(f'{t:<14} {n:>9}')
        sem = [l for l in linhas if l['tipo'] == 'sem resposta']
        if sem:
            partes = [f'{m} {sum(1 for l in sem if l["motivo"] == m)}' for m in MOTIVOS]
            print(f'sem resposta por motivo: {", ".join(partes)}')
    for a, b, j in atencoes:
        print(f'atenção: {a} e {b} são parecidas ({j:.2f}) e estão em grupos diferentes; '
              f'se forem a mesma pergunta, ponha no mesmo grupo')


def classe(linha):
    """O tipo da pergunta; nas sem resposta, o tipo e o motivo, porque cada motivo testa uma coisa."""
    if linha['tipo'] == 'sem resposta':
        return f'sem resposta, {linha["motivo"]}'
    return linha['tipo']


CLASSES = [t for t in TIPOS if t != 'sem resposta'] + [f'sem resposta, {m}' for m in MOTIVOS]


def dividir(linhas, fracao):
    """Retorna (dev, avaliacao) como listas de linhas, na ordem do arquivo."""
    grupos = {}
    for linha in linhas:
        grupos.setdefault(linha['grupo'], []).append(linha)
    por_classe = {}
    for nome, membros in grupos.items():
        # O grupo entra na classe da sua primeira pergunta no arquivo.
        por_classe.setdefault(classe(membros[0]), []).append(nome)
    na_avaliacao = set()
    for nomes in por_classe.values():
        nomes.sort(key=lambda g: hashlib.sha256(g.encode('utf-8')).hexdigest())
        n = len(nomes)
        quantos = 0 if n < 2 else max(1, min(n - 1, round(n * fracao)))
        na_avaliacao.update(nomes[:quantos])
    dev = [l for l in linhas if l['grupo'] not in na_avaliacao]
    aval = [l for l in linhas if l['grupo'] in na_avaliacao]
    return dev, aval


def gravar_csv(caminho, linhas):
    with open(caminho, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, lineterminator='\n')
        w.writeheader()
        for linha in linhas:
            w.writerow({c: linha[c] for c in COLUNAS})


def separar(arquivo, pasta, fracao, caminho_politicas):
    if not 0 < fracao < 1:
        raise ErroEntrada('--avaliacao precisa ficar entre 0 e 1, por exemplo 0.4')
    linhas = ler_csv(arquivo)
    politicas = carregar_politicas(caminho_politicas)
    problemas, _ = checar(linhas, politicas)
    if problemas:
        raise ErroEntrada(f'o conjunto tem {len(problemas)} problema(s); rode "checar" e corrija antes de separar')
    destino = Path(pasta)
    if destino.exists():
        raise ErroEntrada(f'a pasta {pasta} já existe; uma separação nova vai numa pasta nova')
    dev, aval = dividir(linhas, fracao)
    presentes = [c for c in CLASSES if any(classe(l) == c for l in linhas)]
    faltam = [c for c in presentes
              if not (any(classe(l) == c for l in dev) and any(classe(l) == c for l in aval))]
    if faltam:
        raise ErroEntrada(f'{"; ".join(faltam)}: ficou só de um lado; '
                          f'acrescente outro grupo desse tipo antes de separar')
    destino.mkdir(parents=True)
    gravar_csv(destino / 'dev.csv', dev)
    gravar_csv(destino / 'avaliacao.csv', aval)
    ficha = {
        'origem': Path(arquivo).name,
        'origem_sha256': sha256(arquivo),
        'politicas_sha256': sha256(caminho_politicas),
        'fracao_avaliacao': fracao,
        'regra': ('o lado de cada grupo sai do sha256 do nome do grupo, dentro do tipo da primeira '
                  'pergunta do grupo; nas sem resposta, dentro do tipo e do motivo'),
        'dev': {'arquivo': 'dev.csv', 'sha256': sha256(destino / 'dev.csv'),
                'perguntas': len(dev), 'grupos': len({l['grupo'] for l in dev})},
        'avaliacao': {'arquivo': 'avaliacao.csv', 'sha256': sha256(destino / 'avaliacao.csv'),
                      'perguntas': len(aval), 'grupos': len({l['grupo'] for l in aval})},
        'por_tipo': {c: {'dev': sum(1 for l in dev if classe(l) == c),
                         'avaliacao': sum(1 for l in aval if classe(l) == c)}
                     for c in presentes},
    }
    (destino / 'ficha.json').write_text(json.dumps(ficha, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'{len(linhas)} perguntas em {len({l["grupo"] for l in linhas})} grupos; '
          f'avaliação com {fracao:.0%} dos grupos de cada tipo, arredondado')
    print(f'{"tipo":<32} {"dev":>4} {"avaliação":>10}   cada pergunta da avaliação vale')
    for t, c in ficha['por_tipo'].items():
        vale = f'{100 / c["avaliacao"]:.0f} pontos de 100 no tipo'
        print(f'{t:<32} {c["dev"]:>4} {c["avaliacao"]:>10}   {vale}')
    print(f'{"total":<32} {len(dev):>4} {len(aval):>10}')
    print(f'gravado: {pasta}/dev.csv, {pasta}/avaliacao.csv, {pasta}/ficha.json')


def trava(pasta, caminho_politicas):
    ficha_p = Path(pasta) / 'ficha.json'
    try:
        ficha = json.loads(ficha_p.read_text(encoding='utf-8'))
        alvos = [('avaliação', Path(pasta) / ficha['avaliacao']['arquivo'], ficha['avaliacao']['sha256']),
                 ('desenvolvimento', Path(pasta) / ficha['dev']['arquivo'], ficha['dev']['sha256']),
                 ('políticas', Path(caminho_politicas), ficha['politicas_sha256'])]
    except FileNotFoundError:
        raise ErroEntrada(f'não achei {ficha_p}; rode "separar" antes')
    except (json.JSONDecodeError, KeyError, TypeError):
        raise ErroEntrada(f'{ficha_p} está quebrada; separe de novo numa pasta nova')
    mudou = []
    for nome, caminho, esperado in alvos:
        atual = sha256(caminho) if caminho.is_file() else None
        if atual == esperado:
            print(f'igual  {nome:<16} {esperado[:12]}')
        else:
            print(f'MUDOU  {nome:<16} ficha {esperado[:12]}, agora {atual[:12] if atual else "arquivo sumiu"}')
            mudou.append(nome)
    if mudou:
        raise ErroEntrada(f'{", ".join(mudou)} mudou depois da separação; os números medidos com essa '
                          f'ficha não valem mais. Volte o arquivo ou faça uma versão nova do conjunto')
    print('a ficha bate: pode usar a avaliação')


def main(argv=None):
    p = argparse.ArgumentParser(description='Conjunto de referência do assistente da Loja Exemplo.')
    p.add_argument('--politicas', default=str(POLITICAS), help='arquivo das políticas')
    sub = p.add_subparsers(dest='comando')
    c = sub.add_parser('checar', help='aponta as linhas que não servem como pergunta de teste')
    c.add_argument('arquivo')
    c.add_argument('--parecidas', type=float, default=PARECIDAS,
                   help='a partir de quanto duas perguntas de grupos diferentes recebem aviso (0 a 1)')
    s = sub.add_parser('separar', help='divide em desenvolvimento e avaliação')
    s.add_argument('arquivo')
    s.add_argument('--pasta', required=True, help='pasta nova onde gravar dev.csv, avaliacao.csv e ficha.json')
    s.add_argument('--avaliacao', type=float, default=FRACAO, help='parte dos grupos de cada tipo na avaliação')
    t = sub.add_parser('trava', help='diz se algo mudou depois da separação')
    t.add_argument('pasta')
    args = p.parse_args(argv)
    try:
        if args.comando == 'checar':
            if not 0 < args.parecidas <= 1:
                raise ErroEntrada('--parecidas precisa ficar entre 0 e 1')
            linhas = ler_csv(args.arquivo)
            problemas, atencoes = checar(linhas, carregar_politicas(args.politicas), args.parecidas)
            mostrar_checagem(linhas, problemas, atencoes)
            return 2 if problemas else 0
        if args.comando == 'separar':
            separar(args.arquivo, args.pasta, args.avaliacao, args.politicas)
            return 0
        if args.comando == 'trava':
            trava(args.pasta, args.politicas)
            return 0
        raise ErroEntrada('use um dos comandos: checar, separar ou trava')
    except ErroEntrada as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
