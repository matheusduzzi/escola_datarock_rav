"""Roda um juiz de verdade e grava os vereditos no formato que o calibrar.py lê.

Sem rede (não precisa de conta):
    python3 juiz.py notas conversas.csv --estimar --rodadas 5
    python3 juiz.py notas conversas.csv --mostrar s04
    python3 juiz.py pares pares.csv --estimar
    python3 juiz.py pares pares.csv --mostrar p02 --ordem novo-atual

Com um serviço compatível com a API de chat da OpenAI (variáveis JUIZ_BASE_URL e JUIZ_CHAVE):
    python3 juiz.py notas conversas.csv --modelo NOME --rodadas 5 --saida meu-juiz.csv
    python3 juiz.py pares pares.csv --modelo NOME --saida pares-meu-juiz.csv

O programa só grava o arquivo no fim, com todas as chamadas válidas. Resposta fora do formato é
pedida de novo uma vez; se vier errada outra vez, ele para com código 2 e não grava nada.
Só usa a biblioteca padrão do Python 3.9 ou mais novo.
"""
import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

PASTA = Path(__file__).resolve().parent
REGRAS = ('identificacao', 'saude', 'acolhimento')
VEREDITOS = ('cumpre', 'quebra', 'nao-se-aplica')
ORDENS = ('atual-novo', 'novo-atual')


def ler_csv(caminho, colunas):
    with open(caminho, encoding='utf-8', newline='') as f:
        leitor = csv.DictReader(f)
        faltam = [c for c in colunas if c not in (leitor.fieldnames or [])]
        if faltam:
            raise SystemExit(f'erro: {caminho}: faltam colunas {", ".join(faltam)}')
        return list(leitor)


def regras_texto():
    texto = (PASTA / 'regras-atendimento.md').read_text(encoding='utf-8')
    return texto.split('## Como marcar')[0].strip()


def prompt_notas(conversa):
    modelo = (PASTA / 'prompt-notas.md').read_text(encoding='utf-8')
    return (modelo.replace('{regras}', regras_texto())
            .replace('{cliente}', conversa['cliente']).replace('{assistente}', conversa['assistente']))


def prompt_pares(par, ordem):
    modelo = (PASTA / 'prompt-pares.md').read_text(encoding='utf-8')
    primeira, segunda = ordem.split('-')
    return (modelo.replace('{regras}', regras_texto()).replace('{cliente}', par['cliente'])
            .replace('{resposta_1}', par[primeira]).replace('{resposta_2}', par[segunda]))


def ler_json(texto):
    m = re.search(r'\{.*\}', texto or '', flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def valido_notas(obj):
    if not isinstance(obj, dict) or any(obj.get(r) not in VEREDITOS for r in REGRAS):
        return None
    return {r: obj[r] for r in REGRAS}


def valido_pares(obj):
    if not isinstance(obj, dict):
        return None
    e = str(obj.get('escolha', ''))
    return e if e in ('1', '2', 'empate') else None


def chamar(base, chave, modelo, prompt, temperatura):
    corpo = {'model': modelo, 'messages': [{'role': 'user', 'content': prompt}]}
    if temperatura is not None:
        corpo['temperature'] = temperatura
    req = urllib.request.Request(
        base.rstrip('/') + '/chat/completions', data=json.dumps(corpo).encode('utf-8'), method='POST',
        headers={'Authorization': 'Bearer ' + chave, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resposta = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise SystemExit(f'erro: o serviço respondeu {e.code}. Veja o nome do modelo, a chave e o crédito da conta')
    except (urllib.error.URLError, TimeoutError) as e:
        raise SystemExit(f'erro: não consegui falar com {base}: {e}')
    try:
        return resposta['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        raise SystemExit('erro: a resposta do serviço não tem choices[0].message.content')


def julgar(chamadas, validar, args):
    base, chave = os.environ.get('JUIZ_BASE_URL', ''), os.environ.get('JUIZ_CHAVE', '')
    if not base or not chave:
        print('erro: defina JUIZ_BASE_URL e JUIZ_CHAVE antes de rodar o juiz (veja o README da pasta)')
        sys.exit(2)
    if not args.modelo or not args.saida:
        print('erro: use --modelo e --saida para rodar o juiz')
        sys.exit(2)
    resultados = []
    for i, (chave_item, prompt) in enumerate(chamadas, 1):
        valor = None
        for _ in range(2):
            valor = validar(ler_json(chamar(base, chave, args.modelo, prompt, args.temperatura)))
            if valor is not None:
                break
        if valor is None:
            print(f'erro: {chave_item}: o juiz respondeu fora do formato duas vezes; nada foi gravado')
            sys.exit(2)
        resultados.append((chave_item, valor))
        print(f'  {i} de {len(chamadas)}', file=sys.stderr)
    return resultados


def estimar(chamadas, rotulo):
    caracteres = sum(len(p) for _, p in chamadas)
    tokens = round(caracteres / 4)
    print(f'{rotulo}: {len(chamadas)} chamada(s) ao juiz')
    print(f'entrada: {caracteres} caracteres, perto de {tokens} tokens (conta de 4 caracteres por token)')
    print('saída: um JSON curto por chamada. O preço por milhão de tokens está na página do modelo no seu provedor')


def main():
    ap = argparse.ArgumentParser(description='Roda o juiz e grava os vereditos para o calibrar.py.')
    ap.add_argument('modo', choices=('notas', 'pares'))
    ap.add_argument('arquivo')
    ap.add_argument('--estimar', action='store_true', help='conta chamadas e tokens, sem rede')
    ap.add_argument('--mostrar', metavar='ID', help='mostra o prompt de uma conversa ou par, sem rede')
    ap.add_argument('--ordem', choices=ORDENS, default='atual-novo', help='com --mostrar, no modo pares')
    ap.add_argument('--rodadas', type=int, default=5)
    ap.add_argument('--modelo')
    ap.add_argument('--saida')
    ap.add_argument('--temperatura', type=float, default=None,
                    help='se não passar, vale o padrão do serviço')
    args = ap.parse_args()
    if args.rodadas < 1:
        print('erro: --rodadas precisa ser 1 ou mais')
        sys.exit(2)

    if args.modo == 'notas':
        conversas = ler_csv(args.arquivo, ('id', 'cliente', 'assistente'))
        if args.mostrar:
            c = [c for c in conversas if c['id'] == args.mostrar]
            if not c:
                print(f'erro: {args.mostrar} não está em {args.arquivo}')
                sys.exit(2)
            print(prompt_notas(c[0]))
            return
        chamadas = [((r, c['id']), prompt_notas(c)) for r in range(1, args.rodadas + 1) for c in conversas]
        if args.estimar:
            estimar(chamadas, f'{len(conversas)} conversas x {args.rodadas} rodada(s)')
            return
        res = julgar(chamadas, valido_notas, args)
        with open(args.saida, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(('rodada', 'id', 'regra', 'veredito'))
            for (r, cid), v in res:
                for regra in REGRAS:
                    w.writerow((r, cid, regra, v[regra]))
    else:
        pares = ler_csv(args.arquivo, ('par', 'cliente', 'atual', 'novo'))
        if args.mostrar:
            p = [p for p in pares if p['par'] == args.mostrar]
            if not p:
                print(f'erro: {args.mostrar} não está em {args.arquivo}')
                sys.exit(2)
            print(prompt_pares(p[0], args.ordem))
            return
        chamadas = [((p['par'], o), prompt_pares(p, o)) for p in pares for o in ORDENS]
        if args.estimar:
            estimar(chamadas, f'{len(pares)} pares x 2 ordens')
            return
        res = julgar(chamadas, valido_pares, args)
        with open(args.saida, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(('par', 'ordem', 'escolha'))
            for (par, ordem), e in res:
                w.writerow((par, ordem, e))
    print(f'gravado: {args.saida}')


if __name__ == '__main__':
    main()
