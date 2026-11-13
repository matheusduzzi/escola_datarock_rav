"""Compara quatro jeitos de buscar a mesma pergunta nas políticas da Loja Exemplo.

    python3 expandir.py "Quantos dias eu tenho para trocar?" --expansoes expansoes-exemplo.json
    python3 expandir.py "Quantos dias eu tenho para trocar?" --expansoes expansoes-exemplo.json --detalhe
    python3 expandir.py --perguntas perguntas-exemplo.csv --expansoes expansoes-exemplo.json

As quatro estratégias:

  original    BM25 com a pergunta do cliente, como na aula 04.
  multiplas   BM25 com a pergunta e com cada reescrita; as listas se juntam pela
              posição (RRF, constante 60). Cada consulta leva os 5 primeiros
              trechos para a fusão (--por-consulta 0 leva todos). Com
              --sem-original, a pergunta do cliente fica de fora.
  hipotetico  BM25 com o texto de resposta inventado (a ideia do HyDE). O HyDE do
              artigo usa embeddings; aqui a busca é por palavras, para dar para ver
              de qual palavra vem cada ponto.
  q2d         BM25 com a pergunta repetida 5 vezes mais o texto inventado (a forma
              do Query2doc para BM25).

As reescritas e os textos inventados vêm do arquivo de expansões. Nenhum modelo roda
aqui: o arquivo diz quem escreveu cada expansão.

O filtro de perfil, data e status vale para todas as buscas, antes da pontuação.
Só usa a biblioteca padrão do Python 3.9 ou mais novo.
"""
import argparse
import csv
import json
import math
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

PASTA = Path(__file__).resolve().parent
POLITICAS = PASTA.parent / 'dados' / 'politicas' / 'politicas.json'
PERFIS = ('cliente', 'atendimento', 'supervisao', 'financeiro')
ESTRATEGIAS = ('original', 'multiplas', 'hipotetico', 'q2d')
K1 = 1.2
B = 0.75
CONSTANTE = 60
REPETE_Q2D = 5
POR_CONSULTA = 5

# As mesmas palavras de parada do lexical.py da aula 04.
PARADAS = {
    'a', 'o', 'as', 'os', 'um', 'uma', 'de', 'da', 'do', 'das', 'dos', 'e', 'em', 'no', 'na',
    'nos', 'nas', 'ao', 'aos', 'para', 'pra', 'por', 'com', 'que', 'se', 'eu', 'meu', 'minha',
    'me', 'voce', 'voces', 'qual', 'quais', 'quanto', 'quantos', 'quantas', 'como', 'posso',
    'pode', 'ate', 'mais', 'tem', 'ter', 'sao', 'foi', 'esta', 'isso', 'ele', 'ela', 'mas',
    'nao', 'ou', 'sem', 'depois', 'quando', 'onde', 'dar', 'vai', 'sobre',
}


class ErroEntrada(ValueError):
    pass


def termos(texto):
    """Minúsculas, sem acento, palavras e números; tira as palavras de parada."""
    sem = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii').lower()
    return [p for p in re.findall(r'[a-z0-9]+', sem)
            if p not in PARADAS and not (p.isalpha() and len(p) < 2)]


def carregar(caminho=POLITICAS):
    with open(caminho, encoding='utf-8') as f:
        return json.load(f)


def permitidos(trechos, perfil, dia):
    """Trechos aprovados, vigentes na data e que o perfil pode ler. Início entra, fim não."""
    if perfil not in PERFIS:
        raise ErroEntrada(f'perfil desconhecido: {perfil!r} (use {", ".join(PERFIS)})')
    saida = []
    for t in trechos:
        inicio = date.fromisoformat(t['inicio'])
        fim = date.fromisoformat(t['fim']) if t['fim'] else None
        if (t['status'] == 'aprovado' and perfil in t['perfis']
                and inicio <= dia and (fim is None or dia < fim)):
            saida.append(t)
    return saida


def bm25(consulta_termos, trechos, unicos=True):
    """[(pontos, id, partes)] só com quem pontua, do maior para o menor.

    unicos=True conta cada termo da consulta uma vez (como no lexical.py da aula 04).
    unicos=False soma o termo cada vez que ele aparece na consulta: é assim que repetir
    a pergunta 5 vezes no q2d dá mais peso a ela do que ao texto inventado.
    """
    alvo = list(dict.fromkeys(consulta_termos)) if unicos else list(consulta_termos)
    docs = {t['id']: termos(t['titulo'] + ' ' + t['texto']) for t in trechos}
    n = len(docs)
    media = sum(len(d) for d in docs.values()) / n if n else 0
    df = {w: sum(1 for d in docs.values() if w in d) for w in set(alvo)}
    resultado = []
    for tid, d in docs.items():
        pontos, partes = 0.0, {}
        for w in alvo:
            tf = d.count(w)
            if tf == 0:
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            parte = idf * tf / (tf + K1 * (1 - B + B * len(d) / media))
            pontos += parte
            partes[w] = partes.get(w, 0.0) + parte
        if pontos > 0:
            resultado.append((pontos, tid, partes))
    resultado.sort(key=lambda r: (-r[0], r[1]))
    return resultado


def rrf(listas):
    pontos = {}
    for lista in listas:
        for pos, tid in enumerate(lista, 1):
            pontos[tid] = pontos.get(tid, 0.0) + 1 / (CONSTANTE + pos)
    return sorted(((p, t) for t, p in pontos.items()), key=lambda r: (-r[0], r[1]))


def ler_expansoes(caminho):
    try:
        with open(caminho, encoding='utf-8') as f:
            dados = json.load(f)
    except FileNotFoundError:
        raise ErroEntrada(f'arquivo não encontrado: {caminho}')
    except json.JSONDecodeError as e:
        raise ErroEntrada(f'JSON inválido em {caminho}: {e}')
    exp = dados.get('expansoes') if isinstance(dados, dict) else None
    if not isinstance(exp, dict) or not exp:
        raise ErroEntrada('o JSON precisa ter {"expansoes": {"pergunta": {"reescritas": [...], "hipotetico": "..."}}}')
    for pergunta, e in exp.items():
        if not isinstance(e, dict):
            raise ErroEntrada(f'expansão de {pergunta!r} precisa ser um objeto')
        rs = e.get('reescritas')
        if not isinstance(rs, list) or not rs or not all(isinstance(r, str) and termos(r) for r in rs):
            raise ErroEntrada(f'{pergunta!r}: "reescritas" precisa ser uma lista de textos com palavras')
        h = e.get('hipotetico')
        if not isinstance(h, str) or not termos(h):
            raise ErroEntrada(f'{pergunta!r}: "hipotetico" precisa ser um texto com palavras')
    return exp


def buscar(estrategia, pergunta, exp, base, sem_original=False, por_consulta=POR_CONSULTA):
    """Retorna (lista de (pontos, id), custo, origem) para uma estratégia.

    origem: id -> posição do trecho na lista de cada consulta (só em multiplas).
    custo: chamadas ao modelo, buscas, palavras geradas pelo modelo, termos enviados à busca.
    """
    if estrategia == 'original':
        lista = bm25(termos(pergunta), base)
        return [(p, t) for p, t, _ in lista], {'modelo': 0, 'buscas': 1, 'geradas': 0,
                                                 'termos': len(set(termos(pergunta)))}, {}
    if estrategia not in ESTRATEGIAS:
        raise ErroEntrada(f'estratégia desconhecida: {estrategia!r}')
    if exp is None:
        raise ErroEntrada(f'não há expansão para a pergunta {pergunta!r} no arquivo')
    if estrategia == 'multiplas':
        consultas = ([] if sem_original else [pergunta]) + exp['reescritas']
        listas, origem, n_termos = [], {}, 0
        for c in consultas:
            ids = [t for _, t, _ in bm25(termos(c), base)]
            listas.append(ids[:por_consulta] if por_consulta else ids)
            n_termos += len(set(termos(c)))
        for tid in {t for ids in listas for t in ids}:
            origem[tid] = [ids.index(tid) + 1 if tid in ids else None for ids in listas]
        geradas = sum(len(r.split()) for r in exp['reescritas'])
        return rrf(listas), {'modelo': 1, 'buscas': len(consultas), 'geradas': geradas,
                             'termos': n_termos}, origem
    hip = exp['hipotetico']
    if estrategia == 'hipotetico':
        consulta, unicos = termos(hip), True
    else:  # q2d
        consulta, unicos = termos(pergunta) * REPETE_Q2D + termos(hip), False
    lista = bm25(consulta, base, unicos=unicos)
    n = len(set(consulta)) if unicos else len(consulta)
    return [(p, t) for p, t, _ in lista], {'modelo': 1, 'buscas': 1, 'geradas': len(hip.split()),
                                           'termos': n}, {}


def ler_data(texto):
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise ErroEntrada(f'data inválida: {texto!r} (use AAAA-MM-DD)')


def numero(x, casas):
    return f'{x:.{casas}f}'


def mostrar_uma(pergunta, exp, base, args):
    print(f'pergunta: {pergunta}')
    if exp and 'multiplas' in args.estrategias and args.detalhe:
        rotulos = ([] if args.sem_original else ['original']) + [f'r{i}' for i in range(1, len(exp['reescritas']) + 1)]
        for i, r in enumerate(exp['reescritas'], 1):
            print(f'r{i}: {r}')
    for est in args.estrategias:
        lista, custo, origem = buscar(est, pergunta, exp, base, args.sem_original, args.por_consulta)
        nome = est + (' (sem a original)' if est == 'multiplas' and args.sem_original else '')
        print()
        print(f'{nome}: {custo["modelo"]} chamada(s) ao modelo, {custo["buscas"]} busca(s), '
              f'{custo["geradas"]} palavras geradas, {custo["termos"]} termos na busca')
        if not lista:
            print('   nenhum trecho pontuou')
            continue
        casas = 4 if est == 'multiplas' else 3
        for pos, (pts, tid) in enumerate(lista[:args.k], 1):
            print(f'{pos:>3}  {numero(pts, casas):>7}  {tid}')
            if args.detalhe and est == 'multiplas':
                print('          posição em cada consulta: '
                      + ', '.join(f'{r} {p if p else "-"}' for r, p in zip(rotulos, origem[tid])))
        if args.detalhe and est in ('hipotetico', 'q2d'):
            texto = exp['hipotetico']
            consulta = termos(pergunta) * REPETE_Q2D + termos(texto) if est == 'q2d' else termos(texto)
            top = bm25(consulta, base, unicos=(est == 'hipotetico'))[0]
            partes = sorted(top[2].items(), key=lambda kv: -kv[1])[:5]
            print(f'      maiores partes do 1º: '
                  + ', '.join(f'{w} {v:.3f}' for w, v in partes))


def ler_perguntas(caminho, ids):
    try:
        with open(caminho, encoding='utf-8', newline='') as f:
            linhas = list(csv.DictReader(f))
    except FileNotFoundError:
        raise ErroEntrada(f'arquivo não encontrado: {caminho}')
    if not linhas:
        raise ErroEntrada('o CSV não tem nenhuma pergunta')
    faltando = {'id', 'tipo', 'pergunta', 'esperado'} - set(linhas[0])
    if faltando:
        raise ErroEntrada(f'faltam colunas no CSV: {", ".join(sorted(faltando))}')
    for linha in linhas:
        if not (linha['id'] or '').strip() or not (linha['pergunta'] or '').strip():
            raise ErroEntrada(f'linha sem id ou sem pergunta: {linha}')
        if not (linha['tipo'] or '').strip():
            raise ErroEntrada(f'pergunta {linha["id"]} sem tipo')
        esperados = [e.strip() for e in (linha['esperado'] or '').split('|') if e.strip()]
        fora = [e for e in esperados if e not in ids]
        if fora:
            raise ErroEntrada(f'pergunta {linha["id"]}: esperado fora do filtro ou inexistente: '
                              f'{", ".join(fora)}')
        linha['_esperados'] = esperados
    return linhas


def mostrar_varias(linhas, todas_exp, base, args):
    cab = '  '.join(f'{e:>10}' for e in args.estrategias)
    print(f'posição do trecho esperado entre os {args.k} primeiros (1º colocado quando não há esperado)')
    print(f'{"id":<4} {"tipo":<13} {cab}')
    resumo = {e: {} for e in args.estrategias}
    custo_total = {e: {'modelo': 0, 'buscas': 0, 'geradas': 0, 'termos': 0} for e in args.estrategias}
    for linha in linhas:
        celulas = []
        for est in args.estrategias:
            lista, custo, _ = buscar(est, linha['pergunta'], todas_exp.get(linha['pergunta']),
                                     base, args.sem_original, args.por_consulta)
            for c in custo:
                custo_total[est][c] += custo[c]
            topo = [t for _, t in lista[:args.k]]
            if linha['_esperados']:
                pos = next((i for i, t in enumerate(topo, 1) if t in linha['_esperados']), None)
                celulas.append(str(pos) if pos else 'fora')
                caso = ('com', pos)
            else:
                celulas.append(topo[0].split('#')[1][:10] if topo else 'vazia')
                caso = ('sem', bool(topo))
            resumo[est].setdefault(linha['tipo'], []).append(caso)
        print(f'{linha["id"]:<4} {linha["tipo"]:<13} ' + '  '.join(f'{c:>10}' for c in celulas))
    n = len(linhas)
    print()
    print(f'resumo por estratégia (k = {args.k})')
    for est in args.estrategias:
        nome = est + (' sem a original' if est == 'multiplas' and args.sem_original else '')
        print(f'  {nome}')
        for tipo, casos in resumo[est].items():
            com = [p for t, p in casos if t == 'com']
            sem = [v for t, v in casos if t == 'sem']
            partes = []
            if com:
                mrr = sum(1 / p for p in com if p) / len(com)
                partes.append(f'achou {sum(1 for p in com if p)} de {len(com)}, MRR {mrr:.2f}')
            if sem:
                partes.append(f'sem resposta: {sum(1 for v in sem if not v)} de {len(sem)} voltaram vazias')
            print(f'    {tipo:<13} {"; ".join(partes)}')
        c = custo_total[est]
        print(f'    custo em {n} perguntas: {c["modelo"]} chamadas ao modelo, {c["buscas"]} buscas, '
              f'{c["geradas"]} palavras geradas, {c["termos"]} termos enviados à busca')


def main(argv=None):
    p = argparse.ArgumentParser(description='Compara busca original, múltiplas consultas, texto '
                                            'hipotético e q2d nas políticas da Loja Exemplo.')
    p.add_argument('pergunta', nargs='?')
    p.add_argument('--perguntas', help='CSV com id, tipo, pergunta, esperado')
    p.add_argument('--expansoes', required=True, help='JSON com as reescritas e o texto hipotético')
    p.add_argument('--estrategias', default=','.join(ESTRATEGIAS),
                   help='lista separada por vírgula: ' + ','.join(ESTRATEGIAS))
    p.add_argument('--sem-original', action='store_true',
                   help='em multiplas, busca só com as reescritas')
    p.add_argument('--por-consulta', type=int, default=POR_CONSULTA,
                   help='em multiplas, quantos trechos de cada consulta entram na fusão (0 = todos)')
    p.add_argument('--data', default='2026-11-10', help='dia da pergunta, AAAA-MM-DD')
    p.add_argument('--perfil', default='cliente')
    p.add_argument('--k', type=int, default=None)
    p.add_argument('--detalhe', action='store_true')
    args = p.parse_args(argv)
    try:
        if bool(args.pergunta) == bool(args.perguntas):
            raise ErroEntrada('passe uma pergunta entre aspas ou --perguntas arquivo.csv')
        if args.pergunta is not None and not termos(args.pergunta):
            raise ErroEntrada('a pergunta ficou sem nenhum termo depois de tirar as palavras de parada')
        args.estrategias = [e.strip() for e in args.estrategias.split(',') if e.strip()]
        ruins = [e for e in args.estrategias if e not in ESTRATEGIAS]
        if ruins or not args.estrategias:
            raise ErroEntrada(f'estratégia desconhecida: {", ".join(ruins) or "(vazia)"} '
                              f'(use {", ".join(ESTRATEGIAS)})')
        if args.por_consulta < 0:
            raise ErroEntrada('--por-consulta precisa ser 0 (todos) ou mais')
        args.k = args.k if args.k is not None else 3
        if args.k < 1:
            raise ErroEntrada('k precisa ser 1 ou mais')
        dia = ler_data(args.data)
        todas_exp = ler_expansoes(args.expansoes)
        base = permitidos(carregar(), args.perfil, dia)
        ids = {t['id'] for t in base}
        linhas = ler_perguntas(args.perguntas, ids) if args.perguntas else None
        exp = None
        if linhas:
            faltam = [l['id'] for l in linhas if l['pergunta'] not in todas_exp]
            if faltam and any(e != 'original' for e in args.estrategias):
                raise ErroEntrada(f'sem expansão no arquivo para: {", ".join(faltam)}')
        else:
            exp = todas_exp.get(args.pergunta)
            if exp is None and any(e != 'original' for e in args.estrategias):
                raise ErroEntrada(f'não há expansão para a pergunta {args.pergunta!r} no arquivo')
        print(f'filtro: perfil {args.perfil}, data {dia.isoformat()}, '
              f'{len(base)} trechos aprovados e vigentes')
        if linhas:
            mostrar_varias(linhas, todas_exp, base, args)
        else:
            mostrar_uma(args.pergunta, exp, base, args)
    except ErroEntrada as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
