"""Conta os tokens de cada pedaço com o vocabulário de um modelo do tipo BERT, como o all-MiniLM-L6-v2.

    python3 contar_tokens.py --vocab vocab.txt indice.jsonl pedaco-maior-clube.txt

O `vocab.txt` vem da página do modelo no Hugging Face (o README dessa pasta tem o comando). O
programa refaz os dois passos do tokenizador desse modelo: separa as palavras (tudo em minúsculas,
sem acento, pontuação à parte) e quebra cada palavra nos maiores pedaços que existem no vocabulário,
os word pieces. Soma os dois marcadores que o modelo põe no começo e no fim, [CLS] e [SEP].

Aceita o índice (.jsonl, conta o campo "texto" de cada registro) e arquivos de texto (.txt, o
arquivo inteiro). Sai com 1 se algum pedaço passar do --limite (256 por padrão) e com 2 e "erro:"
quando falta arquivo ou o vocabulário não tem [UNK].
Só usa a biblioteca padrão do Python 3.9 ou mais novo.
"""
import argparse
import json
import sys
import unicodedata
from pathlib import Path


class Erro(Exception):
    pass


def ler_vocab(caminho):
    p = Path(caminho)
    if not p.is_file():
        raise Erro(f'arquivo não encontrado: {caminho}')
    vocab = set(p.read_text(encoding='utf-8').split('\n'))
    vocab.discard('')
    if '[UNK]' not in vocab:
        raise Erro(f'{caminho}: não parece um vocab.txt de modelo BERT (falta [UNK])')
    return vocab


def pontuacao(c):
    o = ord(c)
    if 33 <= o <= 47 or 58 <= o <= 64 or 91 <= o <= 96 or 123 <= o <= 126:
        return True
    return unicodedata.category(c).startswith('P')


def palavras(texto):
    # BasicTokenizer com do_lower_case: limpa controle, minúsculas, tira acento, separa pontuação.
    limpo = []
    for c in texto:
        if ord(c) == 0 or ord(c) == 0xFFFD:
            continue
        if c in '\t\n\r' or unicodedata.category(c) == 'Zs':
            limpo.append(' ')
        elif unicodedata.category(c).startswith('C'):
            continue
        else:
            limpo.append(c)
    saida = []
    for w in ''.join(limpo).split():
        w = unicodedata.normalize('NFD', w.lower())
        w = ''.join(c for c in w if unicodedata.category(c) != 'Mn')
        atual = ''
        for c in w:
            if pontuacao(c):
                if atual:
                    saida.append(atual)
                    atual = ''
                saida.append(c)
            else:
                atual += c
        if atual:
            saida.append(atual)
    return saida


def word_pieces(palavra, vocab):
    if len(palavra) > 100:
        return ['[UNK]']
    pecas, ini = [], 0
    while ini < len(palavra):
        fim, achou = len(palavra), None
        while ini < fim:
            sub = palavra[ini:fim] if ini == 0 else '##' + palavra[ini:fim]
            if sub in vocab:
                achou = sub
                break
            fim -= 1
        if achou is None:
            return ['[UNK]']
        pecas.append(achou)
        ini = fim
    return pecas


def tokens(texto, vocab):
    return [p for w in palavras(texto) for p in word_pieces(w, vocab)]


def itens(caminho):
    p = Path(caminho)
    if not p.is_file():
        raise Erro(f'arquivo não encontrado: {caminho}')
    if p.suffix == '.jsonl':
        out = []
        for n, linha in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
            try:
                r = json.loads(linha)
            except json.JSONDecodeError:
                raise Erro(f'{p.name}, linha {n}: JSON inválido')
            if 'pedaco' not in r or 'texto' not in r:
                raise Erro(f'{p.name}, linha {n}: registro sem pedaco ou texto')
            out.append((r['pedaco'], r['texto']))
        return out
    if p.suffix in ('.txt', '.md'):
        return [(p.name, p.read_text(encoding='utf-8'))]
    raise Erro(f'{caminho}: use o índice .jsonl ou um arquivo .txt')


def principal(argv=None):
    ap = argparse.ArgumentParser(prog='contar_tokens.py')
    ap.add_argument('--vocab', required=True)
    ap.add_argument('--limite', type=int, default=256)
    ap.add_argument('--mostrar', type=int, default=5, help='quantos pedaços mostrar, do maior para o menor')
    ap.add_argument('arquivos', nargs='+')
    a = ap.parse_args(argv)
    try:
        vocab = ler_vocab(a.vocab)
        todos = [(nome, texto) for arq in a.arquivos for nome, texto in itens(arq)]
    except Erro as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2
    medidos = []
    for nome, texto in todos:
        t = tokens(texto, vocab)
        medidos.append((len(t) + 2, nome, len(texto), len(texto.split()), t.count('[UNK]')))
    medidos.sort(key=lambda m: (-m[0], m[1]))
    print(f'{len(medidos)} pedaços, limite de {a.limite} tokens contando [CLS] e [SEP]')
    print(f"  {'tokens':>6}  {'caracteres':>10}  {'palavras':>8}  {'tokens/palavra':>14}  pedaço")
    for tk, nome, ch, pl, unk in medidos[:a.mostrar]:
        extra = f'  ({unk} [UNK])' if unk else ''
        print(f"  {tk:>6}  {ch:>10}  {pl:>8}  {f'{tk / pl:.2f}'.replace('.', ','):>14}  {nome}{extra}")
    passam = [m for m in medidos if m[0] > a.limite]
    if passam:
        print(f'{len(passam)} pedaço(s) passam do limite: o modelo corta o fim sem avisar')
        for tk, nome, *_ in passam:
            print(f'  {nome}: {tk} tokens, {tk - a.limite} além do limite')
        return 1
    print(f'cabem no limite: {len(medidos)} de {len(medidos)}')
    return 0


if __name__ == '__main__':
    sys.exit(principal())
