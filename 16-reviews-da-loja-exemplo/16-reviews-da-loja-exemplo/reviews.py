"""Motivo das avaliações de produtos da Loja Exemplo: classificar, buscar exemplos e comparar abordagens.

Três comandos:

    python3 reviews.py palavras --conjunto avaliacao.csv --saida meu-registro-palavras.csv
    python3 reviews.py exemplos --id A07 --conjunto avaliacao.csv --rotuladas avaliacoes-rotuladas.csv
    python3 reviews.py avaliar --conjunto avaliacao.csv --rotuladas avaliacoes-rotuladas.csv \
        --registro registro-palavras.csv --registro registro-modelos.csv \
        --abordagens abordagens.json --precos precos.json --regra regra.json

`palavras` roda a regra de palavras-chave que a loja usa hoje (palavras-chave.json).
`exemplos` mostra as avaliações rotuladas mais parecidas com uma avaliação, pelo BM25 da aula 04.
`avaliar` compara as abordagens nas mesmas avaliações: acerto por motivo, defeitos perdidos,
ganho contra a base com o teste do sinal, custo por mês e a regra escrita antes do teste.

Quando um arquivo tem problema, o programa para com uma linha `erro:` e código 2, sem gravar nada.
Só usa a biblioteca padrão do Python 3.9 ou mais novo.
"""
import argparse
import csv
import io
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

MOTIVOS = ('defeito', 'tamanho', 'entrega', 'diferente', 'atendimento', 'sem_problema')
ROTULO = {'defeito': 'defeito', 'tamanho': 'tamanho', 'entrega': 'entrega', 'diferente': 'diferente',
          'atendimento': 'atendimento', 'sem_problema': 'sem problema'}
K1 = 1.2
B = 0.75
PARADAS = {
    'a', 'o', 'as', 'os', 'um', 'uma', 'de', 'da', 'do', 'das', 'dos', 'e', 'em', 'no', 'na', 'nos',
    'nas', 'ao', 'aos', 'para', 'pra', 'por', 'com', 'que', 'se', 'eu', 'meu', 'minha', 'me', 'mas',
    'nao', 'ou', 'sem', 'foi', 'ele', 'ela', 'isso', 'esta', 'tem', 'ja', 'mais', 'muito', 'bem', 'so',
}


class ErroEntrada(ValueError):
    pass


def normalizar(texto):
    return unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii').lower()


# ---------------------------------------------------------------- leitura dos arquivos

def ler_csv(caminho, colunas):
    try:
        with open(caminho, encoding='utf-8', newline='') as f:
            linhas = list(csv.DictReader(f))
    except FileNotFoundError:
        raise ErroEntrada(f'arquivo não encontrado: {caminho}')
    if linhas and any(c not in linhas[0] for c in colunas):
        faltam = [c for c in colunas if c not in linhas[0]]
        raise ErroEntrada(f'{caminho}: faltam as colunas {", ".join(faltam)}')
    return linhas


def ler_json(caminho):
    try:
        with open(caminho, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise ErroEntrada(f'arquivo não encontrado: {caminho}')
    except json.JSONDecodeError as e:
        raise ErroEntrada(f'{caminho}: JSON inválido ({e.msg}, linha {e.lineno})')


def ler_avaliacoes(caminho, com_motivo=True):
    """Lista de avaliações com id único, texto e, se pedido, o motivo do gabarito dentro da lista."""
    colunas = ['id', 'produto', 'nota', 'texto'] + (['motivo'] if com_motivo else [])
    linhas = ler_csv(caminho, colunas)
    vistos = set()
    for n, l in enumerate(linhas, 2):
        if not (l['id'] or '').strip():
            raise ErroEntrada(f'{caminho}, linha {n}: id vazio')
        if l['id'] in vistos:
            raise ErroEntrada(f'{caminho}: id repetido {l["id"]}')
        vistos.add(l['id'])
        if not (l['texto'] or '').strip():
            raise ErroEntrada(f'{caminho}: {l["id"]} sem texto')
        if com_motivo and l['motivo'] not in MOTIVOS:
            raise ErroEntrada(f'{caminho}: {l["id"]} tem o motivo {l["motivo"]!r}, fora da lista ({", ".join(MOTIVOS)})')
    if not linhas:
        raise ErroEntrada(f'{caminho}: nenhuma avaliação')
    return linhas


# ---------------------------------------------------------------- regra de palavras-chave

def classificar_por_palavras(texto, regras):
    """Primeiro motivo da lista cuja palavra aparece no texto; nenhum, sem problema. Retorna (motivo, palavra)."""
    t = normalizar(texto)
    for item in regras['ordem']:
        for termo in item['termos']:
            if normalizar(termo) in t:
                return item['motivo'], termo
    return regras['sem_palavra'], ''


def cmd_palavras(a):
    regras = ler_json(a.regras)
    for item in regras.get('ordem', []):
        if item.get('motivo') not in MOTIVOS or not item.get('termos'):
            raise ErroEntrada(f'{a.regras}: item sem motivo da lista ou sem termos: {item}')
    if regras.get('sem_palavra') not in MOTIVOS:
        raise ErroEntrada(f'{a.regras}: sem_palavra precisa ser um motivo da lista')
    avaliacoes = ler_avaliacoes(a.conjunto, com_motivo=False)
    if a.mostrar:
        alvo = [l for l in avaliacoes if l['id'] == a.mostrar]
        if not alvo:
            raise ErroEntrada(f'{a.mostrar} não está em {a.conjunto}')
        motivo, termo = classificar_por_palavras(alvo[0]['texto'], regras)
        print(f'{alvo[0]["id"]}: {alvo[0]["texto"]}')
        print(f'palavra que decidiu: {termo or "(nenhuma)"} -> {ROTULO[motivo]}')
        return 0
    saida = io.StringIO()
    w = csv.writer(saida, lineterminator='\n')
    w.writerow(['abordagem', 'id', 'motivo', 'tokens_entrada', 'tokens_saida', 'exemplos'])
    contagem = Counter()
    for l in avaliacoes:
        motivo, _ = classificar_por_palavras(l['texto'], regras)
        contagem[motivo] += 1
        w.writerow(['palavras', l['id'], motivo, 0, 0, ''])
    if a.saida:
        Path(a.saida).write_text(saida.getvalue(), encoding='utf-8')
    print(f'{len(avaliacoes)} avaliações classificadas pela regra de palavras-chave')
    print('  ' + ', '.join(f'{ROTULO[m]} {contagem[m]}' for m in MOTIVOS))
    if a.saida:
        print(f'registro gravado em {a.saida}')
    return 0


# ---------------------------------------------------------------- exemplos parecidos (BM25)

def termos(texto):
    return [p for p in re.findall(r'[a-z0-9]+', normalizar(texto)) if p not in PARADAS and len(p) > 1]


def parecidas(texto, rotuladas, k):
    """As k rotuladas com maior BM25 para o texto; empate decidido pelo id. Retorna [(pontos, linha)]."""
    docs = [(l, termos(l['texto'])) for l in rotuladas]
    n = len(docs)
    media = sum(len(t) for _, t in docs) / n
    df = Counter(p for _, t in docs for p in set(t))
    alvo = list(dict.fromkeys(termos(texto)))
    pontos = []
    for l, t in docs:
        freq = Counter(t)
        s = 0.0
        for p in alvo:
            if freq[p]:
                idf = math.log(1 + (n - df[p] + 0.5) / (df[p] + 0.5))
                s += idf * freq[p] * (K1 + 1) / (freq[p] + K1 * (1 - B + B * len(t) / media))
        if s > 0:
            pontos.append((round(s, 6), l))
    pontos.sort(key=lambda x: (-x[0], x[1]['id']))
    return pontos[:k]


def cmd_exemplos(a):
    avaliacoes = ler_avaliacoes(a.conjunto, com_motivo=False)
    rotuladas = ler_avaliacoes(a.rotuladas)
    alvo = [l for l in avaliacoes if l['id'] == a.id]
    if not alvo:
        raise ErroEntrada(f'{a.id} não está em {a.conjunto}')
    print(f'{alvo[0]["id"]}: {alvo[0]["texto"]}')
    print(f'as {a.k} rotuladas mais parecidas (BM25):')
    for s, l in parecidas(alvo[0]['texto'], rotuladas, a.k):
        print(f'  {l["id"]}  {s:5.2f}  {ROTULO[l["motivo"]]:<12}  {l["texto"]}')
    return 0


# ---------------------------------------------------------------- avaliar

def ler_registros(caminhos, conjunto, rotuladas, abordagens):
    """{abordagem: {id: linha}} com as mesmas avaliações do conjunto e exemplos só das rotuladas."""
    ids = [l['id'] for l in conjunto]
    no_conjunto = set(ids)
    ids_rotuladas = {l['id'] for l in rotuladas}
    registros = {}
    for caminho in caminhos:
        for n, l in enumerate(ler_csv(caminho, ['abordagem', 'id', 'motivo', 'tokens_entrada', 'tokens_saida',
                                                'exemplos']), 2):
            nome = l['abordagem']
            if nome not in abordagens:
                raise ErroEntrada(f'{caminho}, linha {n}: abordagem {nome!r} não está em abordagens.json')
            if l['id'] not in no_conjunto:
                raise ErroEntrada(f'{nome}: {l["id"]} não está no conjunto. Compare só as mesmas avaliações')
            linhas = registros.setdefault(nome, {})
            if l['id'] in linhas:
                raise ErroEntrada(f'{nome}: {l["id"]} aparece duas vezes no registro')
            for campo in ('tokens_entrada', 'tokens_saida'):
                try:
                    valor = int(l[campo])
                except ValueError:
                    valor = -1
                if valor < 0:
                    raise ErroEntrada(f'{nome}: {l["id"]} tem {campo} inválido: {l[campo]!r}')
                l[campo] = valor
            exemplos = (l['exemplos'] or '').split()
            for e in exemplos:
                if e in no_conjunto:
                    raise ErroEntrada(f'{nome}: {l["id"]} usou como exemplo {e}, que está no conjunto de avaliação. '
                                      'Exemplo só pode vir das avaliações rotuladas')
                if e not in ids_rotuladas:
                    raise ErroEntrada(f'{nome}: {l["id"]} usou o exemplo {e}, que não está nas avaliações rotuladas')
            l['exemplos'] = exemplos
            linhas[l['id']] = l
    for nome, linhas in registros.items():
        faltam = [i for i in ids if i not in linhas]
        if faltam:
            raise ErroEntrada(f'{nome}: faltam {len(faltam)} avaliações do conjunto ({", ".join(faltam[:5])})')
    if not registros:
        raise ErroEntrada('nenhum registro lido')
    return registros


def p_sinal(melhor, pior):
    """Teste do sinal exato, bilateral: chance de uma divisão tão desigual se as duas abordagens fossem iguais."""
    n = melhor + pior
    if n == 0:
        return 1.0
    cauda = sum(math.comb(n, k) for k in range(0, min(melhor, pior) + 1)) / 2 ** n
    return min(1.0, 2 * cauda)


def fp(p):
    return 'p < 0.0001' if p < 0.0001 else f'p = {p:.4f}'


def custo(nome, linhas, abordagens, precos, volume):
    """(uso por mês, fixo por mês, montar uma vez, tokens de entrada por avaliação)."""
    cfg = abordagens[nome]
    n = len(linhas)
    entrada = sum(l['tokens_entrada'] for l in linhas.values()) / n
    saida = sum(l['tokens_saida'] for l in linhas.values()) / n
    uso = 0.0
    if cfg.get('modelo'):
        if cfg['modelo'] not in precos['modelos']:
            raise ErroEntrada(f'abordagens.json: {nome} usa o modelo {cfg["modelo"]!r}, que não está em precos.json')
        p = precos['modelos'][cfg['modelo']]
        uso = volume * (entrada * p['entrada_por_milhao'] + saida * p['saida_por_milhao']) / 1e6
    montar = (cfg.get('rotular', 0) / precos['rotuladas_por_hora'] * precos['hora_de_rotular']
              + cfg.get('treino_tokens', 0) * precos['treino_por_milhao_tokens'] / 1e6)
    return uso, float(cfg.get('fixo_mes', 0)), montar, entrada


def tabela(titulo, nomes, linhas, largura=14):
    print(f'{titulo:<15}' + ''.join(f'{n:<{largura}}' for n in nomes))
    for rotulo, valores in linhas:
        print(f'{rotulo:<15}' + ''.join(f'{v:<{largura}}' for v in valores))


def cmd_avaliar(a):
    conjunto = ler_avaliacoes(a.conjunto)
    rotuladas = ler_avaliacoes(a.rotuladas)
    abordagens = ler_json(a.abordagens)
    precos = ler_json(a.precos)
    regra = ler_json(a.regra)
    registros = ler_registros(a.registro, conjunto, rotuladas, abordagens)
    base = regra['base']
    if base not in registros:
        raise ErroEntrada(f'a base da regra, {base!r}, não tem registro')
    nomes = list(registros)
    volume = regra['volume_mes']
    custos = {n: custo(n, registros[n], abordagens, precos, volume) for n in nomes}
    gabarito = {l['id']: l['motivo'] for l in conjunto}
    por_motivo = Counter(gabarito.values())

    print(f'conjunto: {len(conjunto)} avaliações (' +
          ', '.join(f'{por_motivo[m]} {ROTULO[m]}' for m in MOTIVOS) + ')')
    if 'rotulo_a' in conjunto[0] and 'rotulo_b' in conjunto[0]:
        iguais = sum(1 for l in conjunto if l['rotulo_a'] == l['rotulo_b'])
        print(f'gabarito: duas pessoas concordaram em {iguais} de {len(conjunto)}; '
              f'nas {len(conjunto) - iguais} restantes, o guia decidiu')
    print('abordagens: ' + ', '.join(f'{n} ({len(registros[n])})' for n in nomes))
    print()

    certo = {n: {i for i, l in registros[n].items() if l['motivo'] == gabarito[i]} for n in nomes}
    linhas = []
    for m in MOTIVOS:
        linhas.append((ROTULO[m], [f'{sum(1 for i in certo[n] if gabarito[i] == m)}/{por_motivo[m]}' for n in nomes]))
    linhas.append(('total', [f'{len(certo[n])}/{len(conjunto)}' for n in nomes]))
    linhas.append(('acerto', [f'{100 * len(certo[n]) / len(conjunto):.1f}%' for n in nomes]))
    linhas.append(('falso defeito', [str(sum(1 for i, l in registros[n].items()
                                             if l['motivo'] == 'defeito' and gabarito[i] != 'defeito'))
                                     for n in nomes]))
    fora = {n: sum(1 for l in registros[n].values() if l['motivo'] not in MOTIVOS) for n in nomes}
    if any(fora.values()):
        linhas.append(('fora da lista', [str(fora[n]) for n in nomes]))
    tabela('acertos', nomes, linhas)
    print()

    tabela('custo', nomes, [
        ('tokens/aval.', [f'{custos[n][3]:.0f}' for n in nomes]),
        ('R$ uso/mês', [f'{custos[n][0]:.2f}' for n in nomes]),
        ('R$ fixo/mês', [f'{custos[n][1]:.2f}' for n in nomes]),
        ('R$ total/mês', [f'{custos[n][0] + custos[n][1]:.2f}' for n in nomes]),
        ('R$ montar', [f'{custos[n][2]:.2f}' for n in nomes]),
    ])
    print(f'({volume} avaliações por mês; montar = rotular exemplos e treinar, uma vez)')
    print()

    def placar(x, y):
        return len(certo[x] - certo[y]), len(certo[y] - certo[x])

    print(f'regra escrita em {regra["escrita_em"]}, antes do teste (base: {base})')
    passam = []
    defeitos = por_motivo['defeito']
    for n in nomes:
        if n == base:
            continue
        acerto = len(certo[n]) / len(conjunto)
        perdidos = defeitos - sum(1 for i in certo[n] if gabarito[i] == 'defeito')
        ganha, perde = placar(n, base)
        p = p_sinal(ganha, perde)
        total_mes = custos[n][0] + custos[n][1]
        checks = [
            (acerto >= regra['acerto_minimo'],
             f'acerto {100 * acerto:.1f}%, piso {100 * regra["acerto_minimo"]:.0f}%'),
            (perdidos <= regra['defeitos_perdidos_maximo'],
             f'defeito: perdeu {perdidos} de {defeitos}, máximo {regra["defeitos_perdidos_maximo"]}'),
            (ganha > perde and p <= regra['p_maximo'],
             f'ganho sobre {base}: acertou {ganha} que ela errou, errou {perde} que ela acertou, '
             f'{fp(p)}, máximo {regra["p_maximo"]}'),
            (total_mes <= regra['custo_mes_maximo'],
             f'custo R$ {total_mes:.2f} por mês, teto R$ {regra["custo_mes_maximo"]:.2f}'),
        ]
        print(n)
        for ok, texto in checks:
            print(f'  {"ok   " if ok else "FALHA"} {texto}')
        if all(ok for ok, _ in checks):
            passam.append(n)
            print('  passa')
        else:
            print('  não passa')
    print()
    print('escolha')
    if not passam:
        print(f'  nenhuma passa: fica {base}')
        return 0
    passam.sort(key=lambda n: (custos[n][0] + custos[n][1], n))
    barata = passam[0]
    print('  passam: ' + ', '.join(f'{n} (R$ {custos[n][0] + custos[n][1]:.2f})' for n in passam))
    print(f'  a mais barata: {barata}')
    escolhida = barata
    for n in passam[1:]:
        ganha, perde = placar(n, barata)
        p = p_sinal(ganha, perde)
        provado = ganha > perde and p <= regra['p_maximo']
        print(f'  {n} contra {barata}: acertou {ganha} que ela errou, errou {perde} que ela acertou, '
              f'{fp(p)}: ' + ('ganho provado' if provado else 'ganho não provado'))
        if provado and escolhida == barata:
            escolhida = n
    print(f'  escolhida: {escolhida}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Motivo das avaliações de produtos da Loja Exemplo.')
    sub = ap.add_subparsers(dest='comando', required=True)
    p = sub.add_parser('palavras', help='classifica pela regra de palavras-chave de hoje')
    p.add_argument('--conjunto', required=True)
    p.add_argument('--regras', default='palavras-chave.json')
    p.add_argument('--saida')
    p.add_argument('--mostrar', help='id de uma avaliação: mostra a palavra que decidiu')
    p.set_defaults(func=cmd_palavras)
    p = sub.add_parser('exemplos', help='as rotuladas mais parecidas com uma avaliação')
    p.add_argument('--id', required=True)
    p.add_argument('--conjunto', required=True)
    p.add_argument('--rotuladas', default='avaliacoes-rotuladas.csv')
    p.add_argument('-k', type=int, default=5)
    p.set_defaults(func=cmd_exemplos)
    p = sub.add_parser('avaliar', help='compara as abordagens nas mesmas avaliações')
    p.add_argument('--conjunto', required=True)
    p.add_argument('--rotuladas', default='avaliacoes-rotuladas.csv')
    p.add_argument('--registro', action='append', required=True)
    p.add_argument('--abordagens', default='abordagens.json')
    p.add_argument('--precos', default='precos.json')
    p.add_argument('--regra', default='regra.json')
    p.set_defaults(func=cmd_avaliar)
    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except ErroEntrada as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
