"""Busca por palavras com BM25 nas políticas da Loja Exemplo.

Uma pergunta:
    python3 lexical.py "O boleto vence em quantos dias?"
    python3 lexical.py "O boleto vence em quantos dias?" --detalhe

Várias perguntas de um CSV (colunas id, tipo, pergunta, esperado):
    python3 lexical.py --perguntas perguntas-exemplo.csv

Antes de pontuar, o programa filtra os trechos: só os aprovados, vigentes na data
e que o perfil pode ler. A pontuação é a do BM25, com k1 = 1,2 e b = 0,75 e o idf
do Lucene: log(1 + (N - df + 0,5) / (df + 0,5)).

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
K1 = 1.2
B = 0.75

# Palavras que aparecem em quase toda pergunta e não dizem nada do assunto.
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
    saida = []
    for p in re.findall(r'[a-z0-9]+', sem):
        if p in PARADAS:
            continue
        if p.isalpha() and len(p) < 2:
            continue
        saida.append(p)
    return saida


def carregar(caminho=POLITICAS):
    with open(caminho, encoding='utf-8') as f:
        return json.load(f)


def permitidos(trechos, perfil, dia):
    """Trechos que o perfil pode ler na data: aprovados e vigentes. Início entra, fim não entra."""
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


def bm25(pergunta, trechos):
    """Lista de (pontos, id, detalhe) só com quem tem algum termo da pergunta, do maior para o menor."""
    alvo = list(dict.fromkeys(termos(pergunta)))  # termo repetido na pergunta conta uma vez
    docs = {t['id']: termos(t['titulo'] + ' ' + t['texto']) for t in trechos}
    n = len(docs)
    media = sum(len(d) for d in docs.values()) / n if n else 0
    df = {w: sum(1 for d in docs.values() if w in d) for w in alvo}
    resultado = []
    for tid, d in docs.items():
        pontos, detalhe = 0.0, []
        for w in alvo:
            tf = d.count(w)
            if tf == 0:
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            parte = idf * tf / (tf + K1 * (1 - B + B * len(d) / media))
            pontos += parte
            detalhe.append({'termo': w, 'tf': tf, 'df': df[w], 'idf': idf, 'parte': parte})
        if pontos > 0:
            resultado.append((pontos, tid, {'tamanho': len(d), 'media': media, 'termos': detalhe}))
    resultado.sort(key=lambda r: (-r[0], r[1]))
    return alvo, resultado


def ler_data(texto):
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise ErroEntrada(f'data inválida: {texto!r} (use AAAA-MM-DD)')


def validar_k(k):
    if k < 1:
        raise ErroEntrada('k precisa ser 1 ou mais')
    return k


def mostrar_uma(pergunta, base, args):
    if not termos(pergunta):
        raise ErroEntrada('a pergunta ficou sem nenhum termo depois de tirar as palavras de parada')
    alvo, lista = bm25(pergunta, base)
    print(f'pergunta: {pergunta}')
    print(f'termos: {", ".join(alvo)}')
    if not lista:
        print('nenhum trecho tem termo em comum com a pergunta')
        return
    for pos, (pontos, tid, det) in enumerate(lista[:args.k], 1):
        print(f'{pos:>2}  {pontos:6.3f}  {tid}')
        if args.detalhe:
            print(f'      tamanho {det["tamanho"]} termos, média {det["media"]:.2f}')
            for t in det['termos']:
                print(f'      {t["termo"]:<14} tf {t["tf"]}  df {t["df"]}  '
                      f'idf {t["idf"]:.3f}  parte {t["parte"]:.3f}')


def ler_perguntas(caminho):
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
    return linhas


def mostrar_varias(linhas, base, args):
    ids = {t['id'] for t in base}
    print(f'{"id":<5} {"tipo":<14} {"esperado":<26} {"posição":>7}  topo')
    por_tipo = {}
    for linha in linhas:
        esperados = [e.strip() for e in (linha['esperado'] or '').split('|') if e.strip()]
        fora = [e for e in esperados if e not in ids]
        if fora:
            raise ErroEntrada(f'pergunta {linha["id"]}: esperado fora do filtro ou inexistente: '
                              f'{", ".join(fora)}')
        _, lista = bm25(linha['pergunta'], base) if termos(linha['pergunta']) else ([], [])
        topo = lista[:args.k]
        topo_txt = f'{topo[0][1]} ({topo[0][0]:.3f})' if topo else 'nada'
        if esperados:
            pos = next((i for i, r in enumerate(topo, 1) if r[1] in esperados), None)
            pos_txt = str(pos) if pos else 'fora'
            rr = 1 / pos if pos else 0.0
        else:
            pos, pos_txt, rr = None, 'sem resp.', None
        print(f'{linha["id"]:<5} {linha["tipo"]:<14} {("|".join(esperados) or "-"):<26} '
              f'{pos_txt:>7}  {topo_txt}')
        por_tipo.setdefault(linha['tipo'], []).append((esperados, pos, rr, bool(topo)))
    print()
    print(f'resumo com k = {args.k}')
    for tipo, casos in por_tipo.items():
        com = [c for c in casos if c[0]]
        sem = [c for c in casos if not c[0]]
        partes = []
        if com:
            acertos = sum(1 for c in com if c[1])
            mrr = sum(c[2] for c in com) / len(com)
            partes.append(f'achou {acertos} de {len(com)}, MRR {mrr:.2f}')
        if sem:
            vazias = sum(1 for c in sem if not c[3])
            partes.append(f'sem resposta: {vazias} de {len(sem)} voltaram vazias')
        print(f'  {tipo:<14} {"; ".join(partes)}')


def main(argv=None):
    p = argparse.ArgumentParser(description='Busca BM25 nas políticas da Loja Exemplo.')
    p.add_argument('pergunta', nargs='?')
    p.add_argument('--perguntas', help='CSV com id, tipo, pergunta, esperado')
    p.add_argument('--data', default='2026-11-10', help='dia da pergunta, AAAA-MM-DD')
    p.add_argument('--perfil', default='cliente')
    p.add_argument('--k', type=int, default=None, help='quantos resultados mostrar')
    p.add_argument('--detalhe', action='store_true', help='mostra a conta de cada termo')
    args = p.parse_args(argv)
    try:
        if bool(args.pergunta) == bool(args.perguntas):
            raise ErroEntrada('passe uma pergunta entre aspas ou --perguntas arquivo.csv')
        if args.pergunta is not None and not args.pergunta.strip():
            raise ErroEntrada('a pergunta está vazia')
        args.k = validar_k(args.k if args.k is not None else (3 if args.perguntas else 5))
        dia = ler_data(args.data)
        linhas = ler_perguntas(args.perguntas) if args.perguntas else None
        base = permitidos(carregar(), args.perfil, dia)
        print(f'filtro: perfil {args.perfil}, data {dia.isoformat()}, '
              f'{len(base)} trechos aprovados e vigentes')
        if args.perguntas:
            mostrar_varias(linhas, base, args)
        else:
            mostrar_uma(args.pergunta, base, args)
    except ErroEntrada as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
