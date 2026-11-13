"""Mostra as respostas do assistente com os trechos que ele leu e junta as duas perguntas da aula.

Pergunta 1, sobre os trechos: o que a busca trouxe basta para responder? O programa responde
sozinho, comparando os trechos com o trecho esperado de cada pergunta e com o perfil e a data.

Pergunta 2, sobre a resposta: cada frase da resposta está nos trechos? Essa é você que responde,
lendo, no arquivo de classificação. O programa só junta as duas e dá o nome da falha.

    python3 falhas.py mostrar --respostas respostas-semana.csv
    python3 falhas.py mostrar --respostas respostas-semana.csv C02
    python3 falhas.py resumir --respostas respostas-semana.csv --classificacao classificacao-semana.csv

Só biblioteca padrão, Python 3.9 ou mais novo.
"""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
POLITICAS = AQUI.parent / 'dados' / 'politicas' / 'politicas.json'
PERFIS = ('cliente', 'atendimento', 'supervisao', 'financeiro')
COLUNAS = ('id', 'data', 'perfil', 'pergunta', 'esperado', 'trechos', 'resposta', 'confianca')

TRECHOS = {
    'bastam': 'os trechos bastam',
    'faltou': 'faltou trecho',
    'nao-existe': 'a loja não tem regra',
    'conflito': 'trecho que não vale',
}
RESPOSTAS = {
    'apoiada': 'cada frase está nos trechos',
    'contradiz': 'uma frase diz o contrário de um trecho',
    'acrescenta': 'uma frase não está em nenhum trecho',
    'nao-sei': 'diz que não sabe ou o que faltou, sem afirmar além dos trechos',
}
ORDEM = ['certo', 'resposta sem suporte', 'sem suporte e fonte insuficiente', 'responde outra pergunta',
         'recusa à toa', 'fonte insuficiente', 'fonte em conflito']


class Erro(Exception):
    pass


def ler_politicas():
    try:
        trechos = json.loads(POLITICAS.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise Erro(f'não achei as políticas em {POLITICAS}')
    return {t['id']: t for t in trechos}


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
    return [x.strip() for x in campo.split('|') if x.strip()]


def ler_respostas(caminho, politicas):
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
        if not (l['pergunta'] or '').strip() or not (l['resposta'] or '').strip():
            raise Erro(f'{caminho}, {cid}: pergunta ou resposta vazia')
        trechos, esperado = lista(l['trechos'] or ''), lista(l['esperado'] or '')
        if not trechos:
            raise Erro(f'{caminho}, {cid}: nenhum trecho; o registro precisa dizer o que a busca trouxe')
        for t in trechos + esperado:
            if t not in politicas:
                raise Erro(f'{caminho}, {cid}: o trecho {t} não existe nas políticas')
        for t in esperado:
            s = situacao(politicas[t], perfil, dia)
            if s != 'vale':
                raise Erro(f'{caminho}, {cid}: o esperado {t} não vale para {perfil} em {dia} ({s}); '
                           'veja o conjunto de referência')
        try:
            conf = float((l['confianca'] or '').replace(',', '.'))
        except ValueError:
            raise Erro(f'{caminho}, {cid}: confiança "{l["confianca"]}" não é número')
        if not 0 <= conf <= 1:
            raise Erro(f'{caminho}, {cid}: confiança {conf} fora de 0 a 1')
        casos.append({'id': cid, 'data': dia, 'perfil': perfil, 'pergunta': l['pergunta'].strip(),
                      'esperado': esperado, 'trechos': trechos, 'resposta': l['resposta'].strip(),
                      'confianca': conf})
    if not casos:
        raise Erro(f'{caminho}: nenhuma resposta')
    return casos


def eixo_trechos(caso, politicas):
    """Pergunta 1: o que a busca trouxe basta? Não olha a resposta."""
    if any(situacao(politicas[t], caso['perfil'], caso['data']) != 'vale' for t in caso['trechos']):
        return 'conflito'
    if not caso['esperado']:
        return 'nao-existe'
    if all(t in caso['trechos'] for t in caso['esperado']):
        return 'bastam'
    return 'faltou'


def nome_e_conserto(trechos, resposta):
    """Junta as duas perguntas: nome da falha e onde mexer."""
    conserto = []
    if trechos == 'faltou':
        conserto.append('busca')
    if trechos == 'conflito':
        conserto.append('filtro')
    if resposta in ('contradiz', 'acrescenta'):
        conserto.append('resposta')
    elif resposta == 'apoiada' and trechos != 'bastam':
        conserto.append('resposta')
    elif resposta == 'nao-sei' and trechos == 'bastam':
        conserto.append('resposta')
    if trechos == 'conflito':
        nome = 'fonte em conflito'
    elif resposta in ('contradiz', 'acrescenta'):
        nome = 'sem suporte e fonte insuficiente' if trechos == 'faltou' else 'resposta sem suporte'
    elif resposta == 'apoiada':
        nome = 'certo' if trechos == 'bastam' else 'responde outra pergunta'
    else:
        nome = {'bastam': 'recusa à toa', 'faltou': 'fonte insuficiente', 'nao-existe': 'certo'}[trechos]
    return nome, conserto


def ler_classificacao(caminho, ids):
    try:
        with open(caminho, newline='', encoding='utf-8') as f:
            leitor = csv.DictReader(f)
            if not {'id', 'resposta'} <= set(leitor.fieldnames or []):
                raise Erro(f'{caminho}: precisa das colunas id e resposta')
            linhas = list(leitor)
    except FileNotFoundError:
        raise Erro(f'não achei o arquivo {caminho}')
    rotulos = {}
    for l in linhas:
        cid = (l['id'] or '').strip()
        rot = (l['resposta'] or '').strip()
        if cid not in ids:
            raise Erro(f'{caminho}: o id {cid or "(vazio)"} não está no arquivo de respostas')
        if cid in rotulos:
            raise Erro(f'{caminho}: o id {cid} foi classificado duas vezes')
        if not rot:
            raise Erro(f'{caminho}: falta classificar a resposta {cid}')
        if rot not in RESPOSTAS:
            raise Erro(f'{caminho}, {cid}: "{rot}" não é uma classificação da resposta '
                       f'({", ".join(RESPOSTAS)})')
        rotulos[cid] = rot
    faltam = [i for i in ids if i not in rotulos]
    if faltam:
        raise Erro(f'{caminho}: falta classificar {", ".join(faltam)}')
    return rotulos


def num(x):
    return f'{x:.2f}'.replace('.', ',')


def mostrar(casos, politicas, cid):
    if cid is None:
        print(f'{"id":<4} {"perfil":<8} {"data":<10}  {"trechos":<22} pergunta')
        for c in casos:
            print(f'{c["id"]:<4} {c["perfil"]:<8} {c["data"]}  {TRECHOS[eixo_trechos(c, politicas)]:<22} '
                  f'{c["pergunta"]}')
        return
    achados = [c for c in casos if c['id'] == cid]
    if not achados:
        raise Erro(f'o id {cid} não está no arquivo de respostas')
    c = achados[0]
    print(f'{c["id"]}  {c["perfil"]}, {c["data"]}')
    print(f'pergunta: {c["pergunta"]}')
    print(f'esperado: {", ".join(c["esperado"]) or "nenhum (a loja não tem regra sobre isso)"}')
    print('trechos que o assistente leu:')
    for i, t in enumerate(c['trechos'], 1):
        s = situacao(politicas[t], c['perfil'], c['data'])
        marca = '' if s == 'vale' else f'  [NÃO VALE: {s}]'
        print(f'  {i}. {t}{marca}')
        print(f'     {politicas[t]["texto"]}')
    print(f'pergunta 1, os trechos: {TRECHOS[eixo_trechos(c, politicas)]}')
    print(f'resposta (confiança {num(c["confianca"])}):')
    print(f'  {c["resposta"]}')


def resumir(casos, politicas, rotulos):
    print(f'{"id":<4} {"trechos":<11} {"resposta":<11} {"falha":<33} conserto')
    contagem, confs, onde = {}, {}, {}
    for c in casos:
        t = eixo_trechos(c, politicas)
        r = rotulos[c['id']]
        nome, conserto = nome_e_conserto(t, r)
        print(f'{c["id"]:<4} {t:<11} {r:<11} {nome:<33} {" e ".join(conserto) or "-"}')
        contagem[nome] = contagem.get(nome, 0) + 1
        confs.setdefault(nome, []).append(c['confianca'])
        for parte in conserto:
            onde.setdefault(parte, []).append(c['id'])
    print()
    print(f'por falha ({len(casos)} respostas)')
    for nome in ORDEM:
        if nome in contagem:
            v = confs[nome]
            print(f'  {nome:<33} {contagem[nome]:>2}   confiança de {num(min(v))} a {num(max(v))}')
    print()
    print('onde mexer (uma resposta pode contar em dois lugares)')
    for parte in ('resposta', 'busca', 'filtro'):
        ids = onde.get(parte, [])
        print(f'  {parte:<9} {len(ids):>2}   {" ".join(ids)}')
    afirmou = sum(1 for c in casos if rotulos[c['id']] != 'nao-sei')
    certas = sum(1 for c in casos if rotulos[c['id']] != 'nao-sei'
                 and nome_e_conserto(eixo_trechos(c, politicas), rotulos[c['id']])[0] == 'certo')
    recusas = [c for c in casos if rotulos[c['id']] == 'nao-sei']
    recusas_certas = sum(1 for c in recusas if nome_e_conserto(eixo_trechos(c, politicas), 'nao-sei')[0] == 'certo')
    print()
    print(f'afirmou alguma coisa em {afirmou} de {len(casos)}: {certas} certas, {afirmou - certas} com falha')
    print(f'disse que não sabe em {len(recusas)} de {len(casos)}: {recusas_certas} porque a loja não tem regra')


def main(argv=None):
    p = argparse.ArgumentParser(description='Trechos, resposta e o nome da falha.')
    sub = p.add_subparsers(dest='comando')
    m = sub.add_parser('mostrar', help='mostra uma resposta com os trechos que o assistente leu')
    m.add_argument('--respostas', required=True)
    m.add_argument('id', nargs='?')
    r = sub.add_parser('resumir', help='junta os trechos e a sua classificação das respostas')
    r.add_argument('--respostas', required=True)
    r.add_argument('--classificacao', required=True)
    a = p.parse_args(argv)
    if not a.comando:
        p.print_help()
        return 2
    try:
        politicas = ler_politicas()
        casos = ler_respostas(a.respostas, politicas)
        if a.comando == 'mostrar':
            mostrar(casos, politicas, a.id)
        else:
            resumir(casos, politicas, ler_classificacao(a.classificacao, [c['id'] for c in casos]))
    except Erro as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
