"""Indexa as políticas da Loja Exemplo com o id, a versão, as datas, os perfis e o status de cada pedaço.

Comandos, rodados de dentro da pasta da aula:

    python3 indexar.py construir
    python3 indexar.py consultar "Quantos dias eu tenho para trocar?" --perfil cliente --data 2026-11-13
    python3 indexar.py vizinhos "trocas@2#prazo/1"
    python3 indexar.py testar consultas-teste.json
    python3 indexar.py verificar

`construir` lê dados/politicas/politicas.json (a pasta dados/ da raiz do kit) e grava dois arquivos:
o índice (indice.jsonl, um registro por linha) e o manifesto (indice.manifesto.json), que diz com
que modelo, de que arquivo e com que regra de corte o índice foi feito. Com `--lote arquivo.json`,
um trecho do lote com o mesmo id de um trecho que já existe toma o lugar dele, como na aula 01.
Com `--anterior indice.jsonl`, o vetor de um pedaço cujo texto não mudou vem do índice anterior.

O embedding desse programa é feito com pedaços de 3 a 5 letras do texto, espalhados por um hash
(blake2b) em 512 posições, e o vetor tem norma 1. Ele compara letras, não sentido. Serve para ver
o que vai junto do vetor e para refazer o índice byte a byte sem instalar nada.

A consulta filtra antes de ordenar: só concorrem os pedaços aprovados, que o perfil lê e que valem
no dia (o início entra, o fim não). `--filtro depois` ordena tudo, pega os k primeiros e só então
filtra. `--filtro nenhum` não filtra.

Códigos de saída: 0 deu certo; 1 o resultado não serve (teste que falhou, índice que não bate com
as políticas, duas versões da mesma seção valendo no mesmo dia); 2 entrada com defeito, com uma
linha "erro:" e nenhum arquivo gravado.
Só usa a biblioteca padrão do Python 3.9 ou mais novo.
"""
import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
PERFIS = ('cliente', 'atendimento', 'supervisao', 'financeiro')
STATUS = ('aprovado', 'rascunho')
CAMPOS = ('id', 'documento', 'secao', 'versao', 'titulo', 'texto', 'inicio', 'fim', 'perfis', 'status')
LIMITE_PEDACO = 800  # o maior pedaço de estrutura:800, da aula 02
MODELO = {'nome': 'ngramas-hash', 'versao': 1, 'ngramas': [3, 5], 'hash': 'blake2b-64',
          'sinal': 'bit mais alto do hash', 'norma': 1, 'casas': 6}
DIM_PADRAO = 512
FORMATO = 'indice-politicas/1'
ORDEM = ('pedaco', 'trecho', 'documento', 'secao', 'versao', 'titulo', 'inicio', 'fim', 'perfis',
         'status', 'texto', 'texto_sha256', 'vetor')


class Erro(Exception):
    pass


# ---------- leitura ----------

def achar(caminho):
    """Acha o arquivo na pasta atual ou, para caminhos como dados/..., na raiz do kit."""
    p = Path(caminho)
    if not p.is_file() and not p.is_absolute() and (KIT / caminho).is_file():
        return KIT / caminho
    if not p.is_file():
        raise Erro(f'arquivo não encontrado: {caminho}')
    return p


def ler_json(caminho):
    p = achar(caminho)
    try:
        return json.loads(p.read_text(encoding='utf-8')), p
    except json.JSONDecodeError as e:
        raise Erro(f'{caminho}: JSON inválido ({e.msg}, linha {e.lineno})')


def dia(s, onde):
    if not isinstance(s, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        raise Erro(f'{onde}: data fora do formato AAAA-MM-DD: {s!r}')
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise Erro(f'{onde}: data que não existe: {s}')


def validar_trecho(t, onde):
    if not isinstance(t, dict):
        raise Erro(f'{onde}: cada trecho precisa ser um objeto')
    faltam = [c for c in CAMPOS if c not in t]
    if faltam:
        raise Erro(f'{onde}: trecho {t.get("id", "?")} sem o campo {", ".join(faltam)}')
    tid = t['id']
    if not isinstance(t['versao'], int) or isinstance(t['versao'], bool) or t['versao'] < 1:
        raise Erro(f'{onde}: {tid}: versao precisa ser um inteiro a partir de 1')
    if tid != f"{t['documento']}@{t['versao']}#{t['secao']}":
        raise Erro(f'{onde}: o id {tid} não bate com documento, versão e seção '
                   f"({t['documento']}@{t['versao']}#{t['secao']})")
    for c in ('titulo', 'texto'):
        if not isinstance(t[c], str) or not t[c].strip():
            raise Erro(f'{onde}: {tid}: {c} vazio')
    ini = dia(t['inicio'], f'{onde}: {tid}: inicio')
    if t['fim'] is not None and dia(t['fim'], f'{onde}: {tid}: fim') <= ini:
        raise Erro(f'{onde}: {tid}: o fim precisa ser depois do início')
    if t['status'] not in STATUS:
        raise Erro(f'{onde}: {tid}: status {t["status"]!r} (use aprovado ou rascunho)')
    if not isinstance(t['perfis'], list) or not t['perfis']:
        raise Erro(f'{onde}: {tid}: perfis precisa ser uma lista com pelo menos um perfil')
    for p in t['perfis']:
        if p not in PERFIS:
            raise Erro(f'{onde}: {tid}: perfil {p!r} não existe (use {", ".join(PERFIS)})')


def ler_trechos(politicas, lote):
    dados, _ = ler_json(politicas)
    if not isinstance(dados, list) or not dados:
        raise Erro(f'{politicas}: o arquivo precisa ser uma lista de trechos')
    por_id = {}
    for t in dados:
        validar_trecho(t, politicas)
        if t['id'] in por_id:
            raise Erro(f'{politicas}: id repetido: {t["id"]}')
        por_id[t['id']] = t
    if lote:
        ld, _ = ler_json(lote)
        if not isinstance(ld, dict) or not isinstance(ld.get('trechos'), list) or not ld['trechos']:
            raise Erro(f'{lote}: o lote precisa ter a lista "trechos"')
        vistos = set()
        for t in ld['trechos']:
            validar_trecho(t, lote)
            if t['id'] in vistos:
                raise Erro(f'{lote}: id repetido no lote: {t["id"]}')
            vistos.add(t['id'])
            por_id[t['id']] = t
    return [por_id[k] for k in sorted(por_id)]


# ---------- embedding ----------

def normalizar(s):
    s = unicodedata.normalize('NFKD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def embedding(texto, dim):
    s = ' ' + normalizar(texto) + ' '
    v = [0] * dim
    menor, maior = MODELO['ngramas']
    for n in range(menor, maior + 1):
        for i in range(len(s) - n + 1):
            x = int.from_bytes(hashlib.blake2b(s[i:i + n].encode('utf-8'), digest_size=8).digest(), 'big')
            v[x % dim] += 1 if x >> 63 else -1
    norma = math.sqrt(sum(a * a for a in v))
    if norma == 0:
        raise Erro('texto sem letras nem números para virar vetor')
    return [round(a / norma, MODELO['casas']) + 0.0 for a in v]


def cosseno(a, b):
    return sum(x * y for x, y in zip(a, b))


# ---------- índice ----------

def texto_do_pedaco(t):
    # O mesmo texto que o estrutura:800 da aula 02 monta: o caminho dos títulos e o corpo da seção.
    return f"{t['documento']} > {t['titulo']}\n\n{t['texto']}"


def sha_texto(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def sha_arquivo(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def linha(reg):
    return json.dumps({k: reg[k] for k in ORDEM}, ensure_ascii=False, separators=(',', ':'))


def caminho_manifesto(indice):
    p = Path(indice)
    return p.with_name(p.name[:-len('.jsonl')] + '.manifesto.json') if p.name.endswith('.jsonl') else None


def montar(trechos, dim, anteriores=None):
    regs, novos, reaprov = [], [], []
    for t in trechos:
        texto = texto_do_pedaco(t)
        if len(texto) > LIMITE_PEDACO:
            raise Erro(f"{t['id']}: o pedaço tem {len(texto)} caracteres e passa de {LIMITE_PEDACO}; "
                       'corte a seção com o estrutura:800 da aula 02 antes de indexar')
        h = sha_texto(texto)
        if anteriores is not None and h in anteriores:
            vetor = anteriores[h]
            reaprov.append(t['id'])
        else:
            vetor = embedding(texto, dim)
            novos.append(t['id'])
        regs.append({'pedaco': t['id'] + '/1', 'trecho': t['id'], 'documento': t['documento'],
                     'secao': t['secao'], 'versao': t['versao'], 'titulo': t['titulo'],
                     'inicio': t['inicio'], 'fim': t['fim'], 'perfis': list(t['perfis']),
                     'status': t['status'], 'texto': texto, 'texto_sha256': h, 'vetor': vetor})
    return regs, novos, reaprov


def ler_indice(indice):
    p = achar(indice)
    man_p = caminho_manifesto(p)
    if man_p is None:
        raise Erro(f'{indice}: o índice precisa terminar em .jsonl')
    if not man_p.is_file():
        raise Erro(f'{indice}: falta o manifesto {man_p.name}; sem ele não dá para saber como o índice foi feito')
    try:
        man = json.loads(man_p.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise Erro(f'{man_p.name}: JSON inválido ({e.msg}, linha {e.lineno})')
    for c in ('formato', 'modelo', 'dimensao', 'politicas_sha256', 'registros', 'indice_sha256'):
        if c not in man:
            raise Erro(f'{man_p.name}: manifesto sem o campo {c}')
    if man['formato'] != FORMATO:
        raise Erro(f'{man_p.name}: formato {man["formato"]!r} (esse programa lê {FORMATO})')
    regs = []
    for n, bruto in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
        try:
            r = json.loads(bruto)
        except json.JSONDecodeError as e:
            raise Erro(f'{p.name}, linha {n}: JSON inválido ({e.msg})')
        faltam = [c for c in ORDEM if c not in r]
        if faltam:
            raise Erro(f'{p.name}, linha {n}: registro {r.get("pedaco", "?")} sem o campo {", ".join(faltam)}')
        if len(r['vetor']) != man['dimensao']:
            raise Erro(f'{p.name}, linha {n}: vetor com {len(r["vetor"])} posições; o manifesto diz {man["dimensao"]}')
        regs.append(r)
    if not regs:
        raise Erro(f'{p.name}: índice vazio')
    return regs, man, p, man_p


def vale(r, perfil, d):
    if r['status'] != 'aprovado':
        return 'rascunho'
    if perfil not in r['perfis']:
        return f'o perfil {perfil} não lê (lê: {", ".join(r["perfis"])})'
    if date.fromisoformat(r['inicio']) > d:
        return f'ainda não começou (o início é {r["inicio"]})'
    if r['fim'] is not None and date.fromisoformat(r['fim']) <= d:
        return f'a versão acabou (o fim é {r["fim"]})'
    return None


def buscar(regs, man, pergunta, perfil, d, k, filtro):
    q = embedding(pergunta, man['dimensao'])
    ordem = sorted(regs, key=lambda r: (-cosseno(q, r['vetor']), r['pedaco']))
    notas = {r['pedaco']: cosseno(q, r['vetor']) for r in regs}
    if filtro == 'antes':
        validos = [r for r in ordem if vale(r, perfil, d) is None]
        return validos[:k], notas, len(validos), []
    topo = ordem[:k]
    if filtro == 'depois':
        fora = [r for r in topo if vale(r, perfil, d) is not None]
        return [r for r in topo if vale(r, perfil, d) is None], notas, len(regs), fora
    return topo, notas, len(regs), []


def conflitos(regs, perfil, d):
    secoes = {}
    for r in regs:
        if vale(r, perfil, d) is None:
            secoes.setdefault(f"{r['documento']}#{r['secao']}", set()).add(r['versao'])
    return sorted(s for s, vs in secoes.items() if len(vs) > 1)


def virgula(x, casas=3):
    return f'{x:.{casas}f}'.replace('.', ',')


def mostrar_valor(v):
    if v is None:
        return 'sem fim'
    if isinstance(v, list):
        return ', '.join(v)
    return str(v)


def intervalo(r):
    return f"[{r['inicio']}, {r['fim'] or 'sem fim'})"


def curto(s, n=78):
    s = ' '.join(s.split('\n\n', 1)[-1].split())
    return s if len(s) <= n else s[:n - 3].rstrip() + '...'


# ---------- comandos ----------

def cmd_construir(a):
    if a.dim < 16:
        raise Erro('--dim precisa ser pelo menos 16')
    saida = Path(a.saida)
    man_p = caminho_manifesto(saida)
    if man_p is None:
        raise Erro(f'--saida {a.saida}: o índice precisa terminar em .jsonl')
    trechos = ler_trechos(a.politicas, a.lote)
    anteriores, aviso = None, None
    if a.anterior:
        ant, man_ant, _, _ = ler_indice(a.anterior)
        if man_ant['modelo'] == MODELO and man_ant['dimensao'] == a.dim:
            anteriores = {r['texto_sha256']: r['vetor'] for r in ant}
        else:
            aviso = (f'o índice anterior usa outro modelo ou outra dimensão ({man_ant["dimensao"]}); '
                     'nenhum vetor dele foi usado')
            anteriores = {}
        antes = {r['pedaco']: r for r in ant}
    regs, novos, reaprov = montar(trechos, a.dim, anteriores)
    corpo = ''.join(linha(r) + '\n' for r in regs)
    man = {
        'formato': FORMATO,
        'modelo': MODELO,
        'dimensao': a.dim,
        'cortador': f'uma seção por pedaço, com o caminho dos títulos (estrutura:{LIMITE_PEDACO} da aula 02)',
        'politicas': a.politicas.replace('\\', '/'),
        'politicas_sha256': sha_arquivo(achar(a.politicas)),
        'lote': a.lote,
        'lote_sha256': sha_arquivo(achar(a.lote)) if a.lote else None,
        'registros': len(regs),
        'indice_sha256': sha_texto(corpo),
    }
    # Grava bytes, não texto: no Windows, write_text trocaria cada \n por \r\n e o sha256 mudaria.
    saida.write_bytes(corpo.encode('utf-8'))
    man_p.write_bytes((json.dumps(man, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))
    print(f'índice {saida.name}: {len(regs)} registros, {len(novos)} vetores calculados, '
          f'{len(reaprov)} vindos do índice anterior')
    print(f"modelo {MODELO['nome']} v{MODELO['versao']}: pedaços de {MODELO['ngramas'][0]} a "
          f"{MODELO['ngramas'][1]} letras, {a.dim} posições, blake2b, vetor de norma 1")
    print(f"políticas  {man['politicas']}  sha256 {man['politicas_sha256'][:16]}")
    if a.lote:
        print(f"lote       {a.lote}  sha256 {man['lote_sha256'][:16]}")
    print(f"índice     sha256 {man['indice_sha256'][:16]}")
    print(f'manifesto  {man_p.name}')
    if a.anterior:
        if aviso:
            print('atenção: ' + aviso)
        agora = {r['pedaco']: r for r in regs}
        print(f'comparado com {a.anterior}:')
        for pid in sorted(set(agora) | set(antes)):
            if pid not in antes:
                tipo = 'novo'
                det = 'vetor calculado' if pid[:-2] in novos else 'vetor do anterior (mesmo texto)'
            elif pid not in agora:
                tipo, det = 'saiu', ''
            else:
                r0, r1 = antes[pid], agora[pid]
                mud = [c for c in ORDEM if c not in ('vetor',) and r0[c] != r1[c]]
                if not mud:
                    continue
                tipo = 'muda'
                det = ', '.join(f'{c}: {mostrar_valor(r0[c])} -> {mostrar_valor(r1[c])}'
                                if c not in ('texto', 'texto_sha256') else c
                                for c in mud if c != 'texto_sha256')
                det += '; vetor calculado' if pid[:-2] in novos else '; vetor do anterior (mesmo texto)'
            print(f'  {tipo:<5} {pid:<34} {det}')
        iguais = sum(1 for p in agora if p in antes and all(antes[p][c] == agora[p][c] for c in ORDEM))
        print(f'  sem mudança: {iguais}')
    return 0


def cmd_consultar(a):
    regs, man, _, _ = ler_indice(a.indice)
    if a.perfil not in PERFIS:
        raise Erro(f'perfil {a.perfil!r} não existe (use {", ".join(PERFIS)})')
    d = dia(a.data, '--data')
    if a.k < 1:
        raise Erro('--k precisa ser pelo menos 1')
    if not normalizar(a.pergunta):
        raise Erro('a pergunta está vazia')
    res, notas, total, fora = buscar(regs, man, a.pergunta, a.perfil, d, a.k, a.filtro)
    print(f'pergunta: {a.pergunta}')
    if a.filtro == 'antes':
        print(f'perfil {a.perfil} em {a.data}, filtro antes de ordenar: o perfil lê {total} de {len(regs)} '
              f'pedaços nesse dia; mostro {"o primeiro" if a.k == 1 else f"os {a.k} primeiros"}')
    elif a.filtro == 'depois':
        sobra = {0: 'não sobrou nenhum', 1: 'sobrou 1'}.get(len(res), f'sobraram {len(res)}')
        print(f'perfil {a.perfil} em {a.data}, filtro depois de ordenar: ordenei os {len(regs)} pedaços, '
              f'peguei {"o primeiro" if a.k == 1 else f"os {a.k} primeiros"} e filtrei; {sobra}')
    else:
        print(f'sem filtro: {"o primeiro" if a.k == 1 else f"os {a.k} primeiros"} dos {len(regs)} pedaços')
    mostrar = res if a.filtro != 'depois' else sorted(res + fora, key=lambda r: -notas[r['pedaco']])
    for i, r in enumerate(mostrar, 1):
        motivo = vale(r, a.perfil, d)
        marca = '' if motivo is None else f'   fora: {motivo}'
        if a.filtro == 'nenhum':
            marca = '' if motivo is None else f'   o perfil não leria: {motivo}'
        print(f"  {i}  {virgula(notas[r['pedaco']])}  {r['pedaco']:<34} versão {r['versao']}  "
              f"{intervalo(r):<26} {r['status']}{marca}")
        print(f"       {curto(r['texto'])}")
    if not res:
        print('  nenhum pedaço sobrou para o assistente responder')
    if a.filtro == 'antes':
        c = conflitos(regs, a.perfil, d)
        if c:
            print(f'atenção: duas versões aprovadas valem nesse dia em {", ".join(c)}; '
                  'o índice não serve para esse dia')
            return 1
    return 0


def cmd_vizinhos(a):
    regs, _, _, _ = ler_indice(a.indice)
    alvo = next((r for r in regs if r['pedaco'] == a.pedaco), None)
    if alvo is None:
        raise Erro(f'pedaço {a.pedaco} não está no índice')
    if a.k < 1:
        raise Erro('--k precisa ser pelo menos 1')
    outros = sorted((r for r in regs if r is not alvo),
                    key=lambda r: (-cosseno(alvo['vetor'], r['vetor']), r['pedaco']))[:a.k]
    print(f"vizinhos de {alvo['pedaco']}  versão {alvo['versao']}  {intervalo(alvo)}  {alvo['status']}")
    for r in outros:
        print(f"  {virgula(cosseno(alvo['vetor'], r['vetor']))}  {r['pedaco']:<34} versão {r['versao']}  "
              f"{intervalo(r):<26} {r['status']}")
    return 0


def ler_consultas(caminho, regs):
    dados, _ = ler_json(caminho)
    if not isinstance(dados, dict) or not isinstance(dados.get('consultas'), list) or not dados['consultas']:
        raise Erro(f'{caminho}: o arquivo precisa ter a lista "consultas"')
    trechos = {r['trecho'] for r in regs}
    vistos = set()
    for c in dados['consultas']:
        if not isinstance(c, dict):
            raise Erro(f'{caminho}: cada consulta precisa ser um objeto')
        for campo in ('id', 'pergunta', 'perfil', 'data'):
            if not isinstance(c.get(campo), str) or not c[campo].strip():
                raise Erro(f'{caminho}: consulta {c.get("id", "?")} sem o campo {campo}')
        if c['id'] in vistos:
            raise Erro(f'{caminho}: id de consulta repetido: {c["id"]}')
        vistos.add(c['id'])
        if c['perfil'] not in PERFIS:
            raise Erro(f'{caminho}: {c["id"]}: perfil {c["perfil"]!r} não existe')
        dia(c['data'], f'{caminho}: {c["id"]}')
        k = c.get('k', 3)
        if not isinstance(k, int) or isinstance(k, bool) or k < 1:
            raise Erro(f'{caminho}: {c["id"]}: k precisa ser um inteiro a partir de 1')
        nao = c.get('nao_pode', [])
        if not isinstance(nao, list) or not all(isinstance(x, str) for x in nao):
            raise Erro(f'{caminho}: {c["id"]}: nao_pode precisa ser uma lista de ids de trecho')
        if not c.get('primeiro') and not nao:
            raise Erro(f'{caminho}: {c["id"]}: diga o "primeiro" esperado, o "nao_pode" ou os dois')
        for x in nao + ([c['primeiro']] if c.get('primeiro') else []):
            if not re.fullmatch(r'[a-z0-9-]+@\d+#[a-z0-9-]+', x):
                raise Erro(f'{caminho}: {c["id"]}: {x!r} não é um id de trecho como trocas@2#prazo')
    return dados['consultas'], trechos


def cmd_testar(a):
    regs, man, p, _ = ler_indice(a.indice)
    consultas, trechos = ler_consultas(a.consultas, regs)
    print(f'{a.consultas}: {len(consultas)} consultas no índice {p.name}')
    passaram = 0
    for c in consultas:
        d = date.fromisoformat(c['data'])
        k = c.get('k', 3)
        res, _, _, _ = buscar(regs, man, c['pergunta'], c['perfil'], d, k, 'antes')
        ids = [r['trecho'] for r in res]
        erros = []
        if c.get('primeiro'):
            if c['primeiro'] not in trechos:
                erros.append(f"{c['primeiro']} não existe no índice")
            elif not ids or ids[0] != c['primeiro']:
                erros.append(f"esperava {c['primeiro']} em 1º, veio {ids[0] if ids else 'nada'}")
        proibidos = [x for x in c.get('nao_pode', []) if x in ids]
        if proibidos:
            erros.append(f'entre os {k} primeiros não podia vir {", ".join(proibidos)}')
        conf = conflitos(regs, c['perfil'], d)
        if conf:
            erros.append(f'duas versões valem no mesmo dia em {", ".join(conf)}')
        if erros:
            print(f"  FALHA  {c['id']}  {c['perfil']} em {c['data']}: {c['pergunta']}")
            for e in erros:
                print(f'           {e}')
        else:
            passaram += 1
            print(f"  ok     {c['id']}  {c['perfil']} em {c['data']}: {c['pergunta']}")
        print(f"           veio: {', '.join(ids) if ids else 'nada'}")
    print(f'{passaram} de {len(consultas)} consultas passaram')
    return 0 if passaram == len(consultas) else 1


def cmd_verificar(a):
    regs, man, p, man_p = ler_indice(a.indice)
    problemas = []
    if sha_arquivo(p) != man['indice_sha256']:
        problemas.append('o arquivo do índice mudou depois do manifesto (sha256 diferente)')
    if man['modelo'] != MODELO:
        problemas.append(f"o manifesto diz modelo {man['modelo'].get('nome')} v{man['modelo'].get('versao')}; "
                         f"esse programa calcula {MODELO['nome']} v{MODELO['versao']}")
    pol = man.get('politicas') or 'dados/politicas/politicas.json'
    sha_pol = sha_arquivo(achar(pol))
    if sha_pol != man['politicas_sha256']:
        problemas.append(f"{pol} mudou: o manifesto diz sha256 {man['politicas_sha256'][:16]}, "
                         f'o arquivo de hoje tem {sha_pol[:16]}')
    if man.get('lote') and sha_arquivo(achar(man['lote'])) != man.get('lote_sha256'):
        problemas.append(f"o lote {man['lote']} mudou depois do índice")
    refeitos, _, _ = montar(ler_trechos(pol, man.get('lote')), man['dimensao'])
    antes = {r['pedaco']: r for r in regs}
    agora = {r['pedaco']: r for r in refeitos}
    for pid in sorted(set(antes) - set(agora)):
        problemas.append(f'{pid}: está no índice e não sai das políticas de hoje')
    for pid in sorted(set(agora) - set(antes)):
        problemas.append(f'{pid}: sai das políticas de hoje e não está no índice')
    for pid in sorted(set(antes) & set(agora)):
        dif = [c for c in ORDEM if antes[pid][c] != agora[pid][c]]
        if dif:
            problemas.append(f'{pid}: diferente em {", ".join(dif)}')
    if not problemas and sha_texto(''.join(linha(r) + '\n' for r in refeitos)) != sha_arquivo(p):
        problemas.append('refazer não dá o mesmo arquivo, byte a byte (ordem ou formato das linhas)')
    if len(regs) != man['registros']:
        problemas.append(f"o manifesto diz {man['registros']} registros; o índice tem {len(regs)}")
    print(f'verificar {p.name} com {man_p.name}: refiz {len(refeitos)} registros a partir de {pol}'
          + (f" e {man['lote']}" if man.get('lote') else ''))
    if problemas:
        for x in problemas:
            print(f'  diferente: {x}')
        print(f'{len(problemas)} diferença(s): o índice não é o que essas políticas e esse modelo produzem')
        return 1
    print('  índice, manifesto e políticas batem: refazer dá o mesmo arquivo, byte a byte')
    return 0


def principal(argv=None):
    ap = argparse.ArgumentParser(prog='indexar.py', description='Índice das políticas com origem e versão.')
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('construir')
    c.add_argument('--politicas', default='dados/politicas/politicas.json')
    c.add_argument('--lote')
    c.add_argument('--anterior')
    c.add_argument('--dim', type=int, default=DIM_PADRAO)
    c.add_argument('--saida', default='indice.jsonl')
    q = sub.add_parser('consultar')
    q.add_argument('pergunta')
    q.add_argument('--perfil', required=True)
    q.add_argument('--data', required=True)
    q.add_argument('--k', type=int, default=3)
    q.add_argument('--filtro', choices=('antes', 'depois', 'nenhum'), default='antes')
    q.add_argument('--indice', default='indice.jsonl')
    v = sub.add_parser('vizinhos')
    v.add_argument('pedaco')
    v.add_argument('--k', type=int, default=3)
    v.add_argument('--indice', default='indice.jsonl')
    t = sub.add_parser('testar')
    t.add_argument('consultas')
    t.add_argument('--indice', default='indice.jsonl')
    f = sub.add_parser('verificar')
    f.add_argument('--indice', default='indice.jsonl')
    a = ap.parse_args(argv)
    try:
        return {'construir': cmd_construir, 'consultar': cmd_consultar, 'vizinhos': cmd_vizinhos,
                'testar': cmd_testar, 'verificar': cmd_verificar}[a.cmd](a)
    except Erro as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(principal())
