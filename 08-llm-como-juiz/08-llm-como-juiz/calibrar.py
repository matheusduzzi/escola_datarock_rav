"""Compara o juiz automático com as pessoas.

    python3 calibrar.py notas conversas.csv pessoas.csv juiz-mesma.csv juiz-outra.csv
    python3 calibrar.py notas conversas.csv pessoas.csv juiz-mesma.csv juiz-outra.csv --detalhe s04
    python3 calibrar.py pares pares.csv pares-juiz-mesma.csv pares-juiz-outra.csv

notas: cada juiz deu um veredito por conversa e por regra, em várias rodadas. O veredito do juiz é
a maioria das rodadas. O programa conta onde ele concorda com o final das pessoas, que quebras
ele pegou, o que ele reprovou à toa e onde as rodadas não concordam.

pares: cada juiz escolheu a melhor de duas respostas, nas duas ordens. Quando a escolha muda com
a ordem, o par conta como empate.

Arquivo errado: o programa lista os problemas e sai com código 2, sem mostrar números.
Só usa a biblioteca padrão do Python 3.9 ou mais novo.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

REGRAS = ('identificacao', 'saude', 'acolhimento')
VEREDITOS = ('cumpre', 'quebra', 'nao-se-aplica')
ORDENS = ('atual-novo', 'novo-atual')
ESCOLHAS_PESSOAS = ('atual', 'novo', 'empate')
ESCOLHAS_JUIZ = ('1', '2', 'empate')
SEM_MAIORIA = 'sem maioria'


class Problemas(Exception):
    pass


def ler(caminho, colunas, problemas):
    p = Path(caminho)
    if not p.is_file():
        problemas.append(f'{caminho}: arquivo não existe')
        return []
    with p.open(encoding='utf-8', newline='') as f:
        leitor = csv.DictReader(f)
        faltam = [c for c in colunas if c not in (leitor.fieldnames or [])]
        if faltam:
            problemas.append(f'{caminho}: faltam colunas {", ".join(faltam)}')
            return []
        linhas = [{k: (v or '').strip() for k, v in l.items() if k} for l in leitor]
    if not linhas:
        problemas.append(f'{caminho}: arquivo sem linhas')
    return linhas


def parar(problemas):
    print(f'{len(problemas)} problema(s); a calibração só sai com os arquivos certos')
    for p in problemas:
        print('  ' + p)
    sys.exit(2)


def maioria(vereditos):
    c = Counter(vereditos).most_common()
    if len(c) > 1 and c[0][1] == c[1][1]:
        return SEM_MAIORIA, c[0][1]
    return c[0]


def nome_juiz(arquivo):
    n = Path(arquivo).stem
    for prefixo in ('pares-', 'leva2-'):
        if n.startswith(prefixo):
            n = n[len(prefixo):]
    return n


def de(a, b):
    return f'{a} de {b}'


# ------------------------------------------------------------------ notas
def carregar_notas(arq_conversas, arq_pessoas, arqs_juizes):
    problemas = []
    conversas = ler(arq_conversas, ('id', 'cliente', 'assistente'), problemas)
    pessoas = ler(arq_pessoas, ('id', 'regra', 'pessoa_1', 'pessoa_2', 'final'), problemas)
    juizes = {nome_juiz(a): ler(a, ('rodada', 'id', 'regra', 'veredito'), problemas) for a in arqs_juizes}
    if len(juizes) != len(arqs_juizes):
        problemas.append('dois arquivos de juiz com o mesmo nome')
    if problemas:
        raise Problemas(problemas)

    textos = {}
    for l in conversas:
        if l['id'] in textos:
            problemas.append(f'{arq_conversas}: conversa repetida {l["id"]}')
        if not l['cliente'] or not l['assistente']:
            problemas.append(f'{arq_conversas}: {l["id"]}: mensagem vazia')
        textos[l['id']] = l

    marcas = {}
    vazios = {}
    for l in pessoas:
        ch = (l['id'], l['regra'])
        if l['regra'] not in REGRAS:
            problemas.append(f'{arq_pessoas}: {l["id"]}: regra que não existe: {l["regra"]!r}')
            continue
        if l['id'] not in textos:
            problemas.append(f'{arq_pessoas}: {l["id"]} não está em {arq_conversas}')
        if ch in marcas:
            problemas.append(f'{arq_pessoas}: {l["id"]} {l["regra"]} aparece duas vezes')
        for col in ('pessoa_1', 'pessoa_2', 'final'):
            if not l[col]:
                vazios.setdefault(col, []).append(f'{l["id"]} {l["regra"]}')
            elif l[col] not in VEREDITOS:
                problemas.append(f'{arq_pessoas}: {l["id"]} {l["regra"]}: {col} precisa ser '
                                 f'cumpre, quebra ou nao-se-aplica, veio {l[col]!r}')
        marcas[ch] = l
    for col, onde in vazios.items():
        problemas.append(f'{arq_pessoas}: {col} vazio em {len(onde)} item(ns), por exemplo {onde[0]}')
    for cid in textos:
        faltam = [r for r in REGRAS if (cid, r) not in marcas]
        if faltam:
            problemas.append(f'{arq_pessoas}: {cid} sem marcação para {", ".join(faltam)}')

    votos = {}
    for nome, linhas in juizes.items():
        v = {}
        rodadas = set()
        for l in linhas:
            try:
                r = int(l['rodada'])
                if r < 1:
                    raise ValueError
            except ValueError:
                problemas.append(f'{nome}: rodada inválida: {l["rodada"]!r}')
                continue
            ch = (l['id'], l['regra'])
            if ch not in marcas:
                problemas.append(f'{nome}: rodada {r}: {l["id"]} {l["regra"]} não está em {arq_pessoas}')
                continue
            if l['veredito'] not in VEREDITOS:
                problemas.append(f'{nome}: rodada {r}: {l["id"]} {l["regra"]}: veredito precisa ser '
                                 f'cumpre, quebra ou nao-se-aplica, veio {l["veredito"]!r}')
                continue
            if (r, ch) in v:
                problemas.append(f'{nome}: rodada {r}: {l["id"]} {l["regra"]} aparece duas vezes')
            v[(r, ch)] = l['veredito']
            rodadas.add(r)
        for r in sorted(rodadas):
            faltam = [f'{c} {g}' for c, g in marcas if (r, (c, g)) not in v]
            if faltam:
                problemas.append(f'{nome}: rodada {r} sem veredito para {len(faltam)} item(ns), '
                                 f'por exemplo {faltam[0]}')
        votos[nome] = {ch: [v[(r, ch)] for r in sorted(rodadas) if (r, ch) in v] for ch in marcas}
        votos[nome]['_rodadas'] = len(rodadas)
    if problemas:
        raise Problemas(problemas)
    return textos, marcas, votos


def relatorio_notas(arq_conversas, arq_pessoas, arqs_juizes, detalhe=None):
    try:
        textos, marcas, votos = carregar_notas(arq_conversas, arq_pessoas, arqs_juizes)
        if detalhe and detalhe not in textos:
            raise Problemas([f'--detalhe: a conversa {detalhe} não está em {arq_conversas}'])
    except Problemas as e:
        parar(e.args[0])
    nomes = list(votos)
    finais = Counter(m['final'] for m in marcas.values())
    vale = finais['cumpre'] + finais['quebra']
    conc_pp = sum(m['pessoa_1'] == m['pessoa_2'] for m in marcas.values())
    print(f'pessoas {arq_pessoas}: {len(textos)} conversas, {len(REGRAS)} regras ({len(marcas)} itens)')
    print(f'  a regra vale em {vale} itens ({finais["cumpre"]} cumpre, {finais["quebra"]} quebra); '
          f'nos outros {finais["nao-se-aplica"]}, não se aplica')
    print(f'  pessoa 1 e pessoa 2 concordam em {de(conc_pp, len(marcas))}; '
          f'o final decide o(s) {len(marcas) - conc_pp} em que elas discordam')
    print('juízes: ' + ', '.join(f'{n} ({votos[n]["_rodadas"]} rodada(s))' for n in nomes)
          + '; o veredito de cada juiz é a maioria das rodadas')
    print()

    col = 15
    cab = ['identificacao', 'saude', 'acolhimento', 'total']
    print(f'{"contra o final das pessoas":<28}' + ''.join(f'{c:<{col}}' for c in cab))

    def linha(rotulo, por_regra):
        vals = [por_regra(r) for r in REGRAS]
        tot = por_regra(None)
        print(f'{rotulo:<28}' + ''.join(f'{v:<{col}}' for v in vals + [tot]))

    def itens(regra):
        return [(ch, m) for ch, m in marcas.items() if regra is None or ch[1] == regra]

    linha('itens em que a regra vale', lambda r: str(sum(m['final'] in ('cumpre', 'quebra') for _, m in itens(r))))
    linha('quebras no final', lambda r: str(sum(m['final'] == 'quebra' for _, m in itens(r))))
    for n in nomes:
        maj = {ch: maioria(votos[n][ch])[0] for ch in marcas}
        print(n)
        linha('  concorda', lambda r: de(sum(maj[ch] == m['final'] for ch, m in itens(r)), len(itens(r))))
        linha('  quebras que pegou', lambda r: de(sum(m['final'] == 'quebra' and maj[ch] == 'quebra'
                                                      for ch, m in itens(r)),
                                                  sum(m['final'] == 'quebra' for _, m in itens(r))))
        linha('  reprovou o que cumpre', lambda r: str(sum(m['final'] == 'cumpre' and maj[ch] == 'quebra'
                                                           for ch, m in itens(r))))
        linha('  rodadas que não concordam', lambda r: str(sum(len(set(votos[n][ch])) > 1 for ch, _ in itens(r))))
    print('pessoa 1 x pessoa 2')
    linha('  concorda', lambda r: de(sum(m['pessoa_1'] == m['pessoa_2'] for _, m in itens(r)), len(itens(r))))
    print()

    def aprovadas(quebrou):
        return de(sum(not any(quebrou((cid, r)) for r in REGRAS) for cid in textos), len(textos))

    partes = [f'pessoas {aprovadas(lambda ch: marcas[ch]["final"] == "quebra")}']
    for n in nomes:
        partes.append(f'{n} {aprovadas(lambda ch, n=n: maioria(votos[n][ch])[0] == "quebra")}')
    print('conversas sem nenhuma quebra: ' + '; '.join(partes))
    print()

    div = []
    for ch, m in marcas.items():
        maj = {n: maioria(votos[n][ch]) for n in nomes}
        if (m['pessoa_1'] != m['pessoa_2'] or any(maj[n][0] != m['final'] for n in nomes)
                or any(len(set(votos[n][ch])) > 1 for n in nomes)):
            div.append((ch, m, maj))
    print(f'divergências: {len(div)} item(ns) em que as pessoas discordaram, o juiz ficou diferente do final '
          f'ou as rodadas não concordam')
    for (cid, regra), m, maj in div:
        pessoas = 'pessoas ' + (m['pessoa_1'] if m['pessoa_1'] == m['pessoa_2']
                                else f'{m["pessoa_1"]}/{m["pessoa_2"]}')
        juizes = '   '.join(f'{n} {maj[n][0]} {de(maj[n][1], len(votos[n][(cid, regra)]))}' for n in nomes)
        print(f'  {cid}  {regra:<14} final {m["final"]:<14} {pessoas:<23} {juizes}')

    if detalhe:
        t = textos[detalhe]
        print()
        print(f'{detalhe}  cliente: {t["cliente"]}')
        print(f'     assistente: {t["assistente"]}')
        for regra in REGRAS:
            m = marcas[(detalhe, regra)]
            print(f'  {regra:<14} final {m["final"]:<14} pessoa 1 {m["pessoa_1"]}, pessoa 2 {m["pessoa_2"]}')
            for n in nomes:
                print(f'  {"":<14} {n}: ' + ' '.join(votos[n][(detalhe, regra)]))


# ------------------------------------------------------------------ pares
def carregar_pares(arq_pares, arqs_juizes):
    problemas = []
    pares = ler(arq_pares, ('par', 'cliente', 'atual', 'novo', 'pessoas'), problemas)
    juizes = {nome_juiz(a): ler(a, ('par', 'ordem', 'escolha'), problemas) for a in arqs_juizes}
    if len(juizes) != len(arqs_juizes):
        problemas.append('dois arquivos de juiz com o mesmo nome')
    if problemas:
        raise Problemas(problemas)
    ps = {}
    for l in pares:
        if l['par'] in ps:
            problemas.append(f'{arq_pares}: par repetido {l["par"]}')
        if l['pessoas'] not in ESCOLHAS_PESSOAS:
            problemas.append(f'{arq_pares}: {l["par"]}: pessoas precisa ser atual, novo ou empate, '
                             f'veio {l["pessoas"]!r}')
        if not (l['cliente'] and l['atual'] and l['novo']):
            problemas.append(f'{arq_pares}: {l["par"]}: mensagem vazia')
        ps[l['par']] = l
    escolhas = {}
    for nome, linhas in juizes.items():
        e = {}
        for l in linhas:
            if l['par'] not in ps:
                problemas.append(f'{nome}: {l["par"]} não está em {arq_pares}')
                continue
            if l['ordem'] not in ORDENS:
                problemas.append(f'{nome}: {l["par"]}: ordem precisa ser atual-novo ou novo-atual, '
                                 f'veio {l["ordem"]!r}')
                continue
            if l['escolha'] not in ESCOLHAS_JUIZ:
                problemas.append(f'{nome}: {l["par"]} {l["ordem"]}: escolha precisa ser 1, 2 ou empate, '
                                 f'veio {l["escolha"]!r}')
                continue
            if (l['par'], l['ordem']) in e:
                problemas.append(f'{nome}: {l["par"]} {l["ordem"]} aparece duas vezes')
            e[(l['par'], l['ordem'])] = l['escolha']
        for p in ps:
            faltam = [o for o in ORDENS if (p, o) not in e]
            if faltam:
                problemas.append(f'{nome}: {p} sem a ordem {", ".join(faltam)}: rode o par nas duas ordens')
        escolhas[nome] = e
    if problemas:
        raise Problemas(problemas)
    return ps, escolhas


def qual(ordem, escolha):
    """Traduz 1/2 para a resposta que estava naquela posição."""
    if escolha == 'empate':
        return 'empate'
    primeira, segunda = ordem.split('-')
    return primeira if escolha == '1' else segunda


def relatorio_pares(arq_pares, arqs_juizes):
    try:
        ps, escolhas = carregar_pares(arq_pares, arqs_juizes)
    except Problemas as e:
        parar(e.args[0])
    nomes = list(escolhas)
    cont = Counter(p['pessoas'] for p in ps.values())

    def placar(c):
        return f'novo {c["novo"]}, atual {c["atual"]}, empate {c["empate"]}'

    print(f'pares {arq_pares}: {len(ps)} pares; as pessoas escolheram: {placar(cont)}')
    print('cada juiz julgou cada par nas duas ordens: atual-novo (a resposta atual em 1º) e novo-atual')
    print()
    col = 30
    print(f'{"":<34}' + ''.join(f'{n:<{col}}' for n in nomes))
    res = {}
    for n in nomes:
        e = escolhas[n]
        por_par = {}
        for p in ps:
            a, b = qual('atual-novo', e[(p, 'atual-novo')]), qual('novo-atual', e[(p, 'novo-atual')])
            por_par[p] = (a, b, a if a == b else 'empate')
        mudou = [p for p in ps if por_par[p][0] != por_par[p][1]]
        primeira = sum(e[(p, 'atual-novo')] == '1' and e[(p, 'novo-atual')] == '1' for p in mudou)
        res[n] = {
            'iguais': de(len(ps) - len(mudou), len(ps)),
            'primeira': de(primeira, len(mudou)) if mudou else '-',
            'so_an': placar(Counter(v[0] for v in por_par.values())),
            'so_na': placar(Counter(v[1] for v in por_par.values())),
            'duas': placar(Counter(v[2] for v in por_par.values())),
            'conc': de(sum(por_par[p][2] == ps[p]['pessoas'] for p in ps), len(ps)),
            'por_par': por_par, 'mudou': mudou,
        }
    for rot, k in (('mesma escolha nas duas ordens', 'iguais'),
                   ('nas que mudaram, ficou com a 1ª', 'primeira'),
                   ('só na ordem atual-novo', 'so_an'),
                   ('só na ordem novo-atual', 'so_na'),
                   ('nas duas ordens (mudou = empate)', 'duas'),
                   ('concorda com as pessoas', 'conc')):
        print(f'{rot:<34}' + ''.join(f'{res[n][k]:<{col}}' for n in nomes))
    print()
    print('pares em que o juiz mudou de escolha quando a ordem mudou')
    algum = False
    for p in ps:
        for n in nomes:
            if p in res[n]['mudou']:
                a, b, _ = res[n]['por_par'][p]
                print(f'  {p}  pessoas {ps[p]["pessoas"]:<7} {n}: atual-novo deu {a}, novo-atual deu {b}')
                algum = True
    if not algum:
        print('  nenhum')


def main(argv):
    uso = ('uso: python3 calibrar.py notas conversas.csv pessoas.csv juiz.csv [juiz.csv ...] [--detalhe ID]\n'
           '     python3 calibrar.py pares pares.csv juiz.csv [juiz.csv ...]')
    detalhe = None
    if '--detalhe' in argv:
        i = argv.index('--detalhe')
        if i + 1 >= len(argv):
            print(uso)
            return 2
        detalhe = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if len(argv) >= 4 and argv[0] == 'notas':
        relatorio_notas(argv[1], argv[2], argv[3:], detalhe)
        return 0
    if len(argv) >= 3 and argv[0] == 'pares' and not detalhe:
        relatorio_pares(argv[1], argv[2:])
        return 0
    print(uso)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
