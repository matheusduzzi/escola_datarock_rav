"""Mostra o que o assistente pode usar das políticas da Loja Exemplo: por perfil, por dia e por seção.

Três comandos, rodados de dentro da pasta da aula:

    python3 corpus.py ver --perfil cliente --data 2026-11-10
    python3 corpus.py linha trocas#prazo
    python3 corpus.py lote atualizacao-dezembro.json

`ver` e `linha` aceitam `--lote arquivo.json` para mostrar como o corpus fica depois de um lote de
atualização, sem mudar o arquivo das políticas. Um trecho do lote com o mesmo id de um trecho que já
existe toma o lugar dele.

Regras que o programa usa (as mesmas da tarefa 1 do diagnóstico):
- só entra trecho com status "aprovado";
- o perfil precisa estar na lista "perfis" do trecho;
- a versão vale de "inicio" (entra) até "fim" (não entra); "fim" null quer dizer que ainda vale;
- duas versões aprovadas da mesma seção valendo no mesmo dia são um conflito: o comando `ver` para
  com código 1, porque o assistente não teria como escolher.

Entrada com defeito (JSON quebrado, campo faltando, data fora do formato, id que não bate com
documento, versão e seção, perfil ou status desconhecido) para com "erro:" e código 2.
Só usa a biblioteca padrão do Python 3.9 ou mais novo.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

POLITICAS = Path(__file__).resolve().parent.parent / 'dados' / 'politicas' / 'politicas.json'
PERFIS = ('cliente', 'atendimento', 'supervisao', 'financeiro')
STATUS = ('aprovado', 'rascunho')
CAMPOS = ('id', 'documento', 'secao', 'versao', 'titulo', 'texto', 'inicio', 'fim', 'perfis', 'status')


class ErroEntrada(Exception):
    pass


def ler_json(caminho):
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroEntrada(f'arquivo não encontrado: {caminho}')
    try:
        return json.loads(caminho.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise ErroEntrada(f'{caminho.name} não é um JSON válido (linha {e.lineno}): {e.msg}')


def dia(texto, onde):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        raise ErroEntrada(f'{onde}: data {texto!r} fora do formato AAAA-MM-DD')


def validar(t, origem):
    if not isinstance(t, dict):
        raise ErroEntrada(f'{origem}: cada trecho precisa ser um objeto JSON')
    faltam = [c for c in CAMPOS if c not in t]
    rotulo = f'{origem}, trecho {t.get("id", "sem id")!r}'
    if faltam:
        raise ErroEntrada(f'{rotulo}: faltam os campos {", ".join(faltam)}')
    for c in ('id', 'documento', 'secao', 'titulo', 'texto'):
        if not isinstance(t[c], str) or not t[c].strip():
            raise ErroEntrada(f'{rotulo}: o campo {c} está vazio')
    if not isinstance(t['versao'], int) or isinstance(t['versao'], bool) or t['versao'] < 1:
        raise ErroEntrada(f'{rotulo}: a versão precisa ser um número inteiro a partir de 1')
    esperado = f'{t["documento"]}@{t["versao"]}#{t["secao"]}'
    if t['id'] != esperado:
        raise ErroEntrada(f'{rotulo}: o id precisa ser documento@versao#secao, aqui {esperado!r}')
    inicio = dia(t['inicio'], f'{rotulo}, inicio')
    if t['fim'] is not None and dia(t['fim'], f'{rotulo}, fim') <= inicio:
        raise ErroEntrada(f'{rotulo}: o fim ({t["fim"]}) precisa ser depois do início ({t["inicio"]})')
    if t['status'] not in STATUS:
        raise ErroEntrada(f'{rotulo}: status {t["status"]!r} desconhecido (use {" ou ".join(STATUS)})')
    if not isinstance(t['perfis'], list) or any(p not in PERFIS for p in t['perfis']):
        raise ErroEntrada(f'{rotulo}: perfis precisa ser uma lista com {", ".join(PERFIS)}')
    return t


def carregar(politicas=POLITICAS, lote=None):
    """Lista de trechos do corpus; com lote, os trechos do lote entram ou tomam o lugar do mesmo id."""
    base = ler_json(politicas)
    if not isinstance(base, list):
        raise ErroEntrada(f'{Path(politicas).name}: o arquivo precisa ser uma lista de trechos')
    trechos = {}
    for t in base:
        validar(t, Path(politicas).name)
        if t['id'] in trechos:
            raise ErroEntrada(f'{Path(politicas).name}: o id {t["id"]!r} aparece duas vezes')
        trechos[t['id']] = t
    if lote is None:
        return list(trechos.values()), None
    novos = ler_lote(lote)
    mudancas = []
    for t in novos:
        antes = trechos.get(t['id'])
        mudancas.append((t, antes))
        trechos[t['id']] = t
    return list(trechos.values()), mudancas


def ler_lote(caminho):
    dados = ler_json(caminho)
    nome = Path(caminho).name
    if not isinstance(dados, dict) or not isinstance(dados.get('trechos'), list) or not dados['trechos']:
        raise ErroEntrada(f'{nome}: o lote precisa ser um objeto com a lista "trechos", sem ficar vazia')
    vistos = set()
    for t in dados['trechos']:
        validar(t, nome)
        if t['id'] in vistos:
            raise ErroEntrada(f'{nome}: o id {t["id"]!r} aparece duas vezes no lote')
        vistos.add(t['id'])
    return dados['trechos']


def motivo_fora(t, perfil, hoje):
    if t['status'] != 'aprovado':
        return 'rascunho'
    if perfil not in t['perfis']:
        quem = ', '.join(t['perfis']) if t['perfis'] else 'ninguém'
        return f'o perfil {perfil} não lê (lê: {quem})'
    if hoje < date.fromisoformat(t['inicio']):
        return f'ainda não começou (começa em {t["inicio"]})'
    if t['fim'] is not None and hoje >= date.fromisoformat(t['fim']):
        return f'a versão acabou (o fim é {t["fim"]})'
    return None


def ver(trechos, perfil, hoje):
    """(ids que o perfil lê no dia, [(id, motivo)] dos que ficam fora, conflitos por seção)."""
    if perfil not in PERFIS:
        raise ErroEntrada(f'perfil desconhecido: {perfil!r} (use {", ".join(PERFIS)})')
    dentro, fora, por_secao = [], [], {}
    for t in sorted(trechos, key=lambda x: x['id']):
        m = motivo_fora(t, perfil, hoje)
        if m:
            fora.append((t['id'], m))
        else:
            dentro.append(t['id'])
            por_secao.setdefault(f'{t["documento"]}#{t["secao"]}', []).append(t['id'])
    conflitos = {s: ids for s, ids in por_secao.items() if len(ids) > 1}
    return dentro, fora, conflitos


def pl(n, um, varios):
    return f'{n} {um if n == 1 else varios}'


def fmt_intervalo(inicio, fim):
    return f'[{inicio}, {fim if fim else "sem fim"})'


def linha(trechos, secao):
    """Versões da seção em ordem, e buracos e sobreposições entre as aprovadas."""
    if '#' not in secao:
        raise ErroEntrada(f'seção {secao!r}: escreva documento#secao, por exemplo trocas#prazo')
    doc, sec = secao.split('#', 1)
    versoes = sorted((t for t in trechos if t['documento'] == doc and t['secao'] == sec),
                     key=lambda t: (t['inicio'], t['versao']))
    if not versoes:
        raise ErroEntrada(f'seção {secao!r} não existe no corpus')
    avisos = []
    aprovadas = [t for t in versoes if t['status'] == 'aprovado']
    for a, b in zip(aprovadas, aprovadas[1:]):
        fim_a = date.fromisoformat(a['fim']) if a['fim'] else None
        ini_b = date.fromisoformat(b['inicio'])
        if fim_a is not None and ini_b > fim_a:
            dias = (ini_b - fim_a).days
            avisos.append(f'buraco em {fmt_intervalo(a["fim"], b["inicio"])}: {pl(dias, "dia", "dias")} sem versão aprovada '
                          f'entre a versão {a["versao"]} e a {b["versao"]}')
        elif fim_a is None or ini_b < fim_a:
            fins = [x for x in (a['fim'], b['fim']) if x]
            ate = min(fins) if fins else None
            avisos.append(f'sobreposição em {fmt_intervalo(b["inicio"], ate)}: as versões {a["versao"]} e '
                          f'{b["versao"]} valem ao mesmo tempo')
    return versoes, avisos


def mostrar_ver(trechos, perfil, hoje, lote):
    dentro, fora, conflitos = ver(trechos, perfil, hoje)
    if lote:
        print(f'com o lote {Path(lote).name}')
    print(f'perfil {perfil} em {hoje.isoformat()}: lê {len(dentro)} de {len(trechos)} trechos')
    for i in dentro:
        marca = '  !' if any(i in ids for ids in conflitos.values()) else '   '
        print(f'{marca} {i}')
    if fora:
        print(f'fora ({len(fora)}):')
        largura = max(len(i) for i, _ in fora)
        for i, m in fora:
            print(f'    {i:<{largura}}  {m}')
    if conflitos:
        print(f'conflito em {pl(len(conflitos), "seção", "seções")}, ' + ('marcada' if len(conflitos) == 1 else 'marcadas') + ' com !:')
        for s, ids in sorted(conflitos.items()):
            print(f'    {s}: {len(ids)} versões aprovadas valendo no mesmo dia ({", ".join(ids)})')
        print('o assistente não responde com esse corpus nesse dia: corrija as datas antes de indexar')
        return 1
    return 0


def mostrar_linha(trechos, secao, lote):
    versoes, avisos = linha(trechos, secao)
    if lote:
        print(f'com o lote {Path(lote).name}')
    print(f'{secao}: {pl(len(versoes), "versão", "versões")}')
    for t in versoes:
        quem = ', '.join(t['perfis']) if t['perfis'] else 'ninguém'
        print(f'  versão {t["versao"]}  {t["status"]:<8}  {fmt_intervalo(t["inicio"], t["fim"]):<26}  lê: {quem}')
    if avisos:
        for a in avisos:
            print('  ' + a)
    else:
        print('  aprovadas: sem buraco e sem sobreposição')
    return 0


def mostrar_lote(caminho, politicas=POLITICAS):
    trechos, mudancas = carregar(politicas, caminho)
    novos = sum(1 for _, antes in mudancas if antes is None)
    print(f'lote {Path(caminho).name}: {pl(len(mudancas), "trecho", "trechos")} ({pl(novos, "novo", "novos")}, '
          f'{len(mudancas) - novos} com id que já existe)')
    for t, antes in mudancas:
        if antes is None:
            quem = ', '.join(t['perfis']) if t['perfis'] else 'ninguém'
            print(f'  novo  {t["id"]}  {t["status"]}  {fmt_intervalo(t["inicio"], t["fim"])}  lê: {quem}')
            continue
        campos = [c for c in CAMPOS if c != 'id' and t[c] != antes[c]]
        if not campos:
            print(f'  igual {t["id"]}')
            continue
        print(f'  muda  {t["id"]}')
        for c in campos:
            a, d = antes[c], t[c]
            if c == 'perfis':
                a, d = ', '.join(a) or 'ninguém', ', '.join(d) or 'ninguém'
            elif c == 'fim':
                a, d = a or 'sem fim', d or 'sem fim'
            if c == 'texto':
                print(f'        texto antes:  {a}')
                print(f'        texto depois: {d}')
            else:
                print(f'        {c}: {a} -> {d}')
    secoes = sorted({f'{t["documento"]}#{t["secao"]}' for t, _ in mudancas})
    print(f'seções que o lote mexe: {", ".join(secoes)}')
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description='O que o assistente pode usar das políticas da Loja Exemplo.')
    p.add_argument('--politicas', default=str(POLITICAS), help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest='comando')
    pv = sub.add_parser('ver', help='trechos que um perfil lê num dia')
    pv.add_argument('--perfil', required=True)
    pv.add_argument('--data', required=True, help='AAAA-MM-DD')
    pv.add_argument('--lote')
    pl = sub.add_parser('linha', help='versões de uma seção ao longo do tempo')
    pl.add_argument('secao', help='documento#secao, por exemplo trocas#prazo')
    pl.add_argument('--lote')
    pt = sub.add_parser('lote', help='o que um lote de atualização muda')
    pt.add_argument('arquivo')
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        if args.comando is None:
            raise ErroEntrada('escolha um comando: ver, linha ou lote')
        if args.comando == 'lote':
            return mostrar_lote(args.arquivo, args.politicas)
        trechos, _ = carregar(args.politicas, args.lote)
        if args.comando == 'ver':
            return mostrar_ver(trechos, args.perfil, dia(args.data, '--data'), args.lote)
        return mostrar_linha(trechos, args.secao, args.lote)
    except ErroEntrada as e:
        print(f'erro: {e}')
        return 2


if __name__ == '__main__':
    sys.exit(main())
