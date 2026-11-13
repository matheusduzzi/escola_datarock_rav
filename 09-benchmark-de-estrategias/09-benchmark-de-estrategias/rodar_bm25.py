"""Roda o BM25 da aula 04 em todas as perguntas do conjunto e grava o registro.

    python3 rodar_bm25.py --conjunto conjunto-avaliacao.csv --saida meu-registro-bm25.csv

Cada linha do registro tem os 3 primeiros trechos (separados por |), o tempo da busca em
milissegundos, medido no seu computador, e o que a busca gastou de modelo: nada, porque o
BM25 não chama modelo. O filtro é o mesmo da aula 04: perfil cliente, data 2026-11-10.
O ranking sai igual em qualquer computador; o tempo muda de uma máquina para outra.
"""
import argparse
import csv
import sys
import time
from datetime import date

import lexical


def main(argv=None):
    p = argparse.ArgumentParser(description='Registro do BM25 no conjunto.')
    p.add_argument('--conjunto', required=True)
    p.add_argument('--saida', required=True)
    p.add_argument('--data', default='2026-11-10')
    p.add_argument('--perfil', default='cliente')
    p.add_argument('--k', type=int, default=3)
    p.add_argument('--repeticoes', type=int, default=20,
                   help='quantas vezes rodar cada pergunta; o tempo anotado é a mediana')
    args = p.parse_args(argv)
    try:
        if args.k < 1 or args.repeticoes < 1:
            raise lexical.ErroEntrada('k e repeticoes precisam ser 1 ou mais')
        linhas = lexical.ler_perguntas(args.conjunto)
        base = lexical.permitidos(lexical.carregar(), args.perfil, lexical.ler_data(args.data))
    except lexical.ErroEntrada as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2
    saida = []
    for linha in linhas:
        tempos = []
        for _ in range(args.repeticoes):
            inicio = time.perf_counter()
            _, lista = lexical.bm25(linha['pergunta'], base) if lexical.termos(linha['pergunta']) else ([], [])
            tempos.append((time.perf_counter() - inicio) * 1000)
        tempos.sort()
        mediana = tempos[len(tempos) // 2]
        saida.append({'estrategia': 'bm25', 'id': linha['id'],
                      'ranking': '|'.join(tid for _, tid, _ in lista[:args.k]),
                      'tempo_ms': f'{mediana:.3f}', 'tokens_embedding': 0, 'pares_reranker': 0})
    with open(args.saida, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(saida[0]))
        w.writeheader()
        w.writerows(saida)
    print(f'{len(saida)} perguntas gravadas em {args.saida} (filtro: perfil {args.perfil}, '
          f'data {args.data}, {len(base)} trechos)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
