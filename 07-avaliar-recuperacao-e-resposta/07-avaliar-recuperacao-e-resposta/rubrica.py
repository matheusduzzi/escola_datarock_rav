"""Rubrica por componente do assistente da Loja Exemplo: busca e resposta medidas em separado.

    python3 rubrica.py dev.csv registro-k3.csv julgamento-k3.csv
    python3 rubrica.py dev.csv registro-k3.csv julgamento-k3.csv --detalhe c06

Três arquivos de entrada:
    conjunto    o dev.csv da aula 06 (id, grupo, pergunta, perfil, data, tipo, esperados,
                resposta, motivo). As sem resposta têm esperados vazio.
    registro    o que o assistente fez (id, ranking, resposta, certa). ranking são os ids
                dos trechos que a busca passou ao modelo, separados por "|", na ordem.
                certa é a marcação de quem comparou a resposta com a resposta esperada:
                sim ou nao.
    julgamento  a resposta quebrada em afirmações, uma por linha (id, afirmacao, apoio).
                apoio é o id do trecho que diz aquilo, "nenhum" quando nenhum trecho diz,
                ou "recusa" na frase em que o assistente diz que não sabe.

Para cada pergunta, o programa mede:
    relevância  quantos trechos do ranking servem (estão em esperados), de quantos vieram;
    cobertura   quantos trechos esperados vieram no ranking, de quantos são esperados;
    fidelidade  quantas afirmações têm apoio num trecho que veio no ranking, de quantas são.
                Apoio fora do ranking não conta: o modelo não recebeu aquele trecho.
                Número da afirmação que não está no trecho de apoio também não conta.

Uma pergunta com resposta passa quando a cobertura é completa, a fidelidade é completa e a
resposta foi marcada certa. Uma pergunta sem resposta passa quando o assistente recusou e
não afirmou nada sem apoio. Um componente bom não compensa outro que falhou.

Sai com código 2 quando um arquivo tem problema: o programa não mostra nota de arquivo errado.
Só usa a biblioteca padrão do Python 3.9 ou mais novo.
"""
import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

PASTA = Path(__file__).resolve().parent
POLITICAS = PASTA.parent / 'dados' / 'politicas' / 'politicas.json'
COL_CONJUNTO = ['id', 'grupo', 'pergunta', 'perfil', 'data', 'tipo', 'esperados', 'resposta', 'motivo']
COL_REGISTRO = ['id', 'ranking', 'resposta', 'certa']
COL_JULGAMENTO = ['id', 'afirmacao', 'apoio']
SIM_NAO = {'sim': True, 'nao': False, 'não': False}


class ErroEntrada(ValueError):
    pass


def ler_csv(caminho, colunas, nome):
    try:
        with open(caminho, encoding='utf-8', newline='') as f:
            leitor = csv.DictReader(f)
            linhas = list(leitor)
            campos = leitor.fieldnames or []
    except FileNotFoundError:
        raise ErroEntrada(f'arquivo não encontrado: {caminho}')
    faltando = [c for c in colunas if c not in campos]
    if faltando:
        raise ErroEntrada(f'{nome}: faltam colunas: {", ".join(faltando)}')
    if not linhas:
        raise ErroEntrada(f'{nome}: o arquivo não tem nenhuma linha')
    for linha in linhas:
        for c in colunas:
            linha[c] = (linha.get(c) or '').strip()
    return linhas


def carregar_politicas(caminho):
    try:
        with open(caminho, encoding='utf-8') as f:
            return {t['id']: t for t in json.load(f)}
    except FileNotFoundError:
        raise ErroEntrada(f'arquivo de políticas não encontrado: {caminho}')
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ErroEntrada(f'arquivo de políticas quebrado: {caminho} ({e})')


def lista(campo):
    return [x.strip() for x in campo.split('|') if x.strip()]


def numeros(texto):
    return re.findall(r'\d+(?:[.,]\d+)*', texto)


def tem_numero(n, texto):
    return re.search(r'(?<![\d.,])' + re.escape(n) + r'(?![\d]|[.,]\d)', texto) is not None


def vale(trecho, perfil, dia):
    """O mesmo filtro da busca: aprovado, vigente na data (início entra, fim não) e lido pelo perfil."""
    inicio = date.fromisoformat(trecho['inicio'])
    fim = date.fromisoformat(trecho['fim']) if trecho['fim'] else None
    return (trecho['status'] == 'aprovado' and perfil in trecho['perfis']
            and inicio <= dia and (fim is None or dia < fim))


def ler_tudo(arq_conjunto, arq_registro, arq_julgamento, politicas):
    """Lê e valida os três arquivos. Retorna (perguntas, problemas). perguntas: lista na ordem do conjunto."""
    problemas = []
    conjunto = ler_csv(arq_conjunto, COL_CONJUNTO, 'conjunto')
    registro = ler_csv(arq_registro, COL_REGISTRO, 'registro')
    julgamento = ler_csv(arq_julgamento, COL_JULGAMENTO, 'julgamento')

    perguntas, por_id = [], {}
    for c in conjunto:
        if not c['id']:
            problemas.append(('conjunto', 'linha sem id'))
            continue
        if c['id'] in por_id:
            problemas.append((c['id'], 'id repetido no conjunto'))
            continue
        try:
            dia = date.fromisoformat(c['data'])
        except ValueError:
            problemas.append((c['id'], f'data inválida no conjunto: {c["data"]!r}'))
            continue
        p = {'id': c['id'], 'tipo': c['tipo'], 'perfil': c['perfil'], 'dia': dia,
             'esperados': lista(c['esperados']), 'sem_resposta': not lista(c['esperados']),
             'registro': None, 'afirmacoes': []}
        for e in p['esperados']:
            if e not in politicas:
                problemas.append((c['id'], f'trecho esperado {e} não existe nas políticas'))
        perguntas.append(p)
        por_id[c['id']] = p

    for r in registro:
        p = por_id.get(r['id'])
        if p is None:
            problemas.append((r['id'] or 'registro', 'id do registro não está no conjunto'))
            continue
        if p['registro'] is not None:
            problemas.append((r['id'], 'pergunta repetida no registro'))
            continue
        ranking = lista(r['ranking'])
        if len(set(ranking)) != len(ranking):
            problemas.append((r['id'], 'o mesmo trecho aparece duas vezes no ranking'))
        for t in ranking:
            if t not in politicas:
                problemas.append((r['id'], f'trecho {t} do ranking não existe nas políticas'))
            elif not vale(politicas[t], p['perfil'], p['dia']):
                problemas.append((r['id'], f'trecho {t} do ranking não passa no filtro de {p["perfil"]} '
                                           f'em {p["dia"].isoformat()}: a busca esqueceu o filtro'))
        if r['certa'].lower() not in SIM_NAO:
            problemas.append((r['id'], f'certa precisa ser sim ou nao, veio {r["certa"]!r}'))
        if not r['resposta']:
            problemas.append((r['id'], 'resposta vazia no registro'))
        p['registro'] = {'ranking': ranking, 'resposta': r['resposta'],
                         'certa': SIM_NAO.get(r['certa'].lower())}

    for j in julgamento:
        p = por_id.get(j['id'])
        if p is None:
            problemas.append((j['id'] or 'julgamento', 'id do julgamento não está no conjunto'))
            continue
        if not j['afirmacao']:
            problemas.append((j['id'], 'afirmação vazia no julgamento'))
            continue
        apoio = j['apoio']
        if not apoio:
            problemas.append((j['id'], f'apoio vazio em «{j["afirmacao"]}»: use o id do trecho, nenhum ou recusa'))
            continue
        if apoio not in ('nenhum', 'recusa') and apoio not in politicas:
            problemas.append((j['id'], f'apoio {apoio} não existe nas políticas'))
            continue
        p['afirmacoes'].append({'texto': j['afirmacao'], 'apoio': apoio})

    sem_registro = [p['id'] for p in perguntas if p['registro'] is None]
    if sem_registro:
        problemas.append(('registro', f'{len(sem_registro)} pergunta(s) sem registro: {", ".join(sem_registro)}'))
    sem_julgamento = [p['id'] for p in perguntas if not p['afirmacoes']]
    if sem_julgamento:
        problemas.append(('julgamento', f'{len(sem_julgamento)} pergunta(s) sem julgamento: '
                                        f'{", ".join(sem_julgamento)}'))
    return perguntas, problemas


def avaliar(p, politicas):
    """Notas de uma pergunta. Retorna dict com os componentes, o veredito e os avisos."""
    ranking = p['registro']['ranking']
    avisos, apoiadas, contadas = [], 0, 0
    recusou = any(a['apoio'] == 'recusa' for a in p['afirmacoes'])
    for n, a in enumerate(p['afirmacoes'], 1):
        a['conta'] = False
        if a['apoio'] == 'recusa':
            continue
        contadas += 1
        if a['apoio'] == 'nenhum':
            continue
        if a['apoio'] not in ranking:
            avisos.append(f'afirmação {n} aponta {a["apoio"]}, que não veio na busca: conta como sem apoio')
            continue
        faltam = [x for x in numeros(a['texto']) if not tem_numero(x, politicas[a['apoio']]['texto'])]
        if faltam:
            avisos.append(f'afirmação {n}: o número {faltam[0]} não está em {a["apoio"]}: conta como sem apoio')
            continue
        a['conta'] = True
        apoiadas += 1
    servem = sum(1 for t in ranking if t in p['esperados'])
    vieram = sum(1 for e in p['esperados'] if e in ranking)
    certa = p['registro']['certa']
    falhas = []
    if not p['sem_resposta'] and vieram < len(p['esperados']):
        falhas.append('busca: faltou trecho')
    if apoiadas < contadas:
        falhas.append('resposta: afirmação sem apoio')
    if p['sem_resposta']:
        if not recusou:
            falhas.append('resposta: devia recusar')
        if certa and not recusou:
            avisos.append('marcada certa, mas a pergunta não tem resposta e o assistente não recusou')
        if certa is False and recusou:
            avisos.append('marcada errada, mas a pergunta não tem resposta e o assistente recusou')
    else:
        if recusou:
            falhas.append('resposta: recusou com resposta nas políticas')
        if certa is False and not falhas:
            falhas.append('resposta: fiel, mas errada')
    passa = not falhas
    return {'servem': servem, 'ranking': len(ranking), 'vieram': vieram, 'esperados': len(p['esperados']),
            'apoiadas': apoiadas, 'contadas': contadas, 'recusou': recusou, 'certa': certa,
            'passa': passa, 'falhas': falhas, 'avisos': avisos}


def mostrar(perguntas, politicas, nome_conjunto, nome_registro, detalhe):
    notas = {p['id']: avaliar(p, politicas) for p in perguntas}
    k = max((len(p['registro']['ranking']) for p in perguntas), default=0)
    com = [p for p in perguntas if not p['sem_resposta']]
    sem = [p for p in perguntas if p['sem_resposta']]
    print(f'conjunto {nome_conjunto}: {len(perguntas)} perguntas ({len(com)} com resposta, {len(sem)} sem resposta)')
    print(f'registro {nome_registro}: até {k} trecho(s) por pergunta')
    print()
    print(f'{"id":<5} {"tipo":<13} {"relevância":<11} {"cobertura":<10} {"fidelidade":<11} {"certa":<6} '
          f'{"rubrica":<8} onde falhou')
    for p in perguntas:
        n = notas[p['id']]
        rel = '-' if p['sem_resposta'] else f'{n["servem"]} de {n["ranking"]}'
        cob = '-' if p['sem_resposta'] else f'{n["vieram"]} de {n["esperados"]}'
        fid = 'recusou' if n['recusou'] and n['contadas'] == 0 else f'{n["apoiadas"]} de {n["contadas"]}'
        certa = 'sim' if n['certa'] else 'não'
        print(f'{p["id"]:<5} {p["tipo"]:<13} {rel:<11} {cob:<10} {fid:<11} {certa:<6} '
              f'{"passa" if n["passa"] else "falha":<8} {"; ".join(n["falhas"])}'.rstrip())
    avisos = [(p['id'], a) for p in perguntas for a in notas[p['id']]['avisos']]
    if avisos:
        print()
        for pid, a in avisos:
            print(f'atenção: {pid}: {a}')
    print()
    print('resumo')
    servem = sum(notas[p['id']]['servem'] for p in com)
    ranking = sum(notas[p['id']]['ranking'] for p in com)
    completas = sum(1 for p in com if notas[p['id']]['vieram'] == notas[p['id']]['esperados'])
    apoiadas = sum(n['apoiadas'] for n in notas.values())
    contadas = sum(n['contadas'] for n in notas.values())
    recusadas = sum(1 for p in sem if notas[p['id']]['recusou'])
    certas = sum(1 for n in notas.values() if n['certa'])
    passam = sum(1 for n in notas.values() if n['passa'])
    print(f'  busca     trechos que servem: {servem} de {ranking} que vieram, nas {len(com)} perguntas com resposta')
    print(f'            cobertura completa: {completas} de {len(com)}')
    print(f'  resposta  afirmações com apoio na busca: {apoiadas} de {contadas}')
    print(f'            sem resposta recusadas: {recusadas} de {len(sem)}')
    print(f'  marcadas certas: {certas} de {len(perguntas)}')
    print(f'  passam na rubrica: {passam} de {len(perguntas)}')
    if detalhe:
        p = next((x for x in perguntas if x['id'] == detalhe), None)
        if p is None:
            raise ErroEntrada(f'--detalhe: a pergunta {detalhe} não está no conjunto')
        print()
        print(f'{p["id"]}  esperados: {" | ".join(p["esperados"]) or "nenhum (sem resposta)"}')
        print(f'      ranking: {" | ".join(p["registro"]["ranking"]) or "nada"}')
        print(f'      resposta: {p["registro"]["resposta"]}')
        for i, a in enumerate(p['afirmacoes'], 1):
            marca = 'recusa' if a['apoio'] == 'recusa' else ('apoio' if a['conta'] else 'sem apoio')
            print(f'      {i}. [{marca}] {a["texto"]}  ({a["apoio"]})')
    return notas


def main(argv=None):
    p = argparse.ArgumentParser(description='Rubrica por componente: busca e resposta medidas em separado.')
    p.add_argument('conjunto', help='o dev.csv da aula 06')
    p.add_argument('registro', help='o que o assistente fez: id, ranking, resposta, certa')
    p.add_argument('julgamento', help='as afirmações de cada resposta: id, afirmacao, apoio')
    p.add_argument('--detalhe', metavar='ID', help='mostra o ranking e as afirmações de uma pergunta')
    p.add_argument('--politicas', default=str(POLITICAS), help='arquivo das políticas')
    args = p.parse_args(argv)
    try:
        politicas = carregar_politicas(args.politicas)
        perguntas, problemas = ler_tudo(args.conjunto, args.registro, args.julgamento, politicas)
        if problemas:
            print(f'{len(problemas)} problema(s); a rubrica só sai com os arquivos certos')
            for onde, texto in problemas:
                print(f'  {onde:<10} {texto}')
            return 2
        mostrar(perguntas, politicas, Path(args.conjunto).name, Path(args.registro).name, args.detalhe)
        return 0
    except ErroEntrada as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
