"""Corta um documento em pedaços e mostra o que cada jeito de cortar faz com as respostas.

Rode de dentro da pasta 02-chunking:

    python3 cortar.py comparar regulamento-clube.md --perguntas perguntas-exemplo.json tamanho:500 estrutura:800
    python3 cortar.py listar regulamento-clube.md estrutura:800
    python3 cortar.py ver regulamento-clube.md tamanho:500 --perguntas perguntas-exemplo.json --pergunta C3
    python3 cortar.py ver dados/politicas/politicas.json tamanho:500 --pedaco trocas~1

Jeitos de cortar:

    tamanho:N      corta o documento inteiro a cada N caracteres, sem partir palavra
    tamanho:N:S    o mesmo, e cada pedaço começa repetindo uns S caracteres do anterior
    estrutura:L    corta nos títulos (## e ###). Se um pedaço passa de L caracteres, corta
                   por parágrafo, depois por linha da tabela ou item da lista, depois por frase.
                   Cada pedaço começa com os títulos de onde veio e leva os campos da seção.

O documento pode ser um .md com o cabeçalho de campos (como regulamento-clube.md) ou o
politicas.json do kit, em que cada trecho é uma seção. Caminhos que começam com dados/
são procurados também na raiz do kit, como dados/politicas/politicas.json.

O programa não busca nada e não chama modelo: ele corta e conta.
Sai com 0 quando roda e com 2 quando a entrada está errada.
"""
import json
import re
import statistics
import sys
import textwrap
import unicodedata
from pathlib import Path

CAMPOS = ('documento', 'versao', 'inicio', 'fim', 'perfis', 'status')


class Erro(Exception):
    pass


def junta(s):
    return ' '.join(s.split())


def slug(titulo):
    s = unicodedata.normalize('NFD', titulo.lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


# ---------------------------------------------------------------- leitura

def ler_markdown(caminho, texto):
    if not texto.startswith('---\n'):
        raise Erro(f'{caminho}: o arquivo precisa começar com o cabeçalho de campos entre linhas ---')
    fim_cab = texto.find('\n---\n', 4)
    if fim_cab < 0:
        raise Erro(f'{caminho}: o cabeçalho de campos não fecha com uma linha ---')
    campos = {}
    for linha in texto[4:fim_cab].splitlines():
        if not linha.strip():
            continue
        if ':' not in linha:
            raise Erro(f'{caminho}: linha do cabeçalho sem ":": {linha!r}')
        k, v = linha.split(':', 1)
        campos[k.strip()] = v.strip()
    faltam = [c for c in CAMPOS if c not in campos]
    if faltam:
        raise Erro(f'{caminho}: faltam campos no cabeçalho: {", ".join(faltam)}')
    if not campos['versao'].isdigit():
        raise Erro(f'{caminho}: versao precisa ser um número inteiro')
    for c in ('inicio', 'fim'):
        if campos[c] and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', campos[c]):
            raise Erro(f'{caminho}: {c} precisa estar no formato AAAA-MM-DD')
    if not campos['inicio']:
        raise Erro(f'{caminho}: inicio vazio')
    base = {'documento': campos['documento'], 'versao': int(campos['versao']), 'inicio': campos['inicio'],
            'fim': campos['fim'] or None, 'perfis': [p.strip() for p in campos['perfis'].split(',') if p.strip()],
            'status': campos['status']}
    if not base['perfis']:
        raise Erro(f'{caminho}: perfis vazio')

    raw = texto[fim_cab + 5:].lstrip('\n')
    m = re.search(r'^# (.+)$', raw, flags=re.M)
    if not m:
        raise Erro(f'{caminho}: falta o título do documento (linha que começa com "# ")')
    titulo_doc = m.group(1).strip()
    inicios = [h for h in re.finditer(r'^## (.+)$', raw, flags=re.M)]
    if not inicios:
        raise Erro(f'{caminho}: o documento não tem seções (linhas que começam com "## ")')
    secoes = []
    vistos = set()
    for i, h in enumerate(inicios):
        a = 0 if i == 0 else h.start()
        b = inicios[i + 1].start() if i + 1 < len(inicios) else len(raw)
        titulo = h.group(1).strip()
        sec = slug(titulo)
        if sec in vistos:
            raise Erro(f'{caminho}: duas seções com o mesmo título: {titulo}')
        vistos.add(sec)
        corpo = raw[h.end():b].strip('\n')
        if not corpo.strip():
            raise Erro(f'{caminho}: a seção "{titulo}" está vazia')
        secoes.append(dict(base, secao=sec, titulo=titulo, id=f"{base['documento']}@{base['versao']}#{sec}",
                           caminho=[titulo_doc, titulo], corpo=corpo, a=a, b=b))
    return [{'nome': base['documento'], 'raw': raw, 'secoes': secoes}]


def ler_politicas(caminho, texto):
    try:
        trechos = json.loads(texto)
    except json.JSONDecodeError as e:
        raise Erro(f'{caminho}: JSON inválido ({e.msg}, linha {e.lineno})')
    if not isinstance(trechos, list) or not trechos:
        raise Erro(f'{caminho}: o arquivo precisa ser uma lista de trechos')
    grupos = {}
    for t in trechos:
        if not isinstance(t, dict) or any(k not in t for k in ('id', 'titulo', 'texto') + CAMPOS):
            raise Erro(f'{caminho}: trecho sem os campos id, titulo, texto e {", ".join(CAMPOS)}')
        g = grupos.setdefault(t['documento'], {'nome': t['documento'], 'partes': [], 'secoes': []})
        bloco = f"## {t['titulo']}\n\n{t['texto']}"
        a = sum(len(p) + 2 for p in g['partes'])
        g['partes'].append(bloco)
        g['secoes'].append({**{k: t[k] for k in CAMPOS}, 'secao': t.get('secao', slug(t['titulo'])),
                            'titulo': t['titulo'], 'id': t['id'], 'caminho': [t['documento'], t['titulo']],
                            'corpo': t['texto'], 'a': a, 'b': a + len(bloco)})
    for g in grupos.values():
        g['raw'] = '\n\n'.join(g.pop('partes'))
    return list(grupos.values())


def achar(caminho):
    """Acha o arquivo na pasta atual ou, para caminhos como dados/..., na raiz do kit."""
    p = Path(caminho)
    if not p.is_file() and not p.is_absolute():
        no_kit = Path(__file__).resolve().parent.parent / caminho
        if no_kit.is_file():
            return no_kit
    if not p.is_file():
        raise Erro(f'arquivo não encontrado: {caminho}')
    return p


def ler(caminho):
    p = achar(caminho)
    texto = p.read_text(encoding='utf-8')
    if p.suffix == '.md':
        return ler_markdown(caminho, texto)
    if p.suffix == '.json':
        return ler_politicas(caminho, texto)
    raise Erro(f'{caminho}: use um .md com cabeçalho de campos ou o politicas.json')


def ler_perguntas(caminho, grupos):
    p = Path(caminho)
    if not p.is_file():
        raise Erro(f'arquivo não encontrado: {caminho}')
    try:
        dados = json.loads(p.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise Erro(f'{caminho}: JSON inválido ({e.msg}, linha {e.lineno})')
    perguntas = dados.get('perguntas') if isinstance(dados, dict) else None
    if not isinstance(perguntas, list) or not perguntas:
        raise Erro(f'{caminho}: falta a lista "perguntas"')
    todo = junta(' '.join(g['raw'] for g in grupos))
    ids = set()
    for q in perguntas:
        if not isinstance(q, dict) or not q.get('id') or not isinstance(q.get('precisa'), list) or not q['precisa']:
            raise Erro(f'{caminho}: cada pergunta precisa de "id" e de uma lista "precisa" não vazia')
        if q['id'] in ids:
            raise Erro(f'{caminho}: id de pergunta repetido: {q["id"]}')
        ids.add(q['id'])
        for parte in q['precisa']:
            if not isinstance(parte, str) or not parte.strip():
                raise Erro(f'{caminho}: a pergunta {q["id"]} tem um texto vazio em "precisa"')
            if junta(parte) not in todo:
                raise Erro(f'{caminho}: a pergunta {q["id"]} pede um texto que não está no documento: {parte!r}')
    return perguntas


# ---------------------------------------------------------------- jeitos de cortar

def ler_jeito(s):
    m = re.fullmatch(r'tamanho:(\d+)(?::(\d+))?', s)
    if m:
        n, sob = int(m.group(1)), int(m.group(2) or 0)
        if n < 50:
            raise Erro(f'{s}: o tamanho mínimo é 50 caracteres')
        if sob >= n:
            raise Erro(f'{s}: a sobreposição precisa ser menor que o tamanho')
        return {'nome': s, 'tipo': 'tamanho', 'n': n, 'sob': sob}
    m = re.fullmatch(r'estrutura:(\d+)', s)
    if m:
        lim = int(m.group(1))
        if lim < 100:
            raise Erro(f'{s}: o limite mínimo é 100 caracteres')
        return {'nome': s, 'tipo': 'estrutura', 'lim': lim}
    raise Erro(f'jeito de cortar desconhecido: {s!r} (use tamanho:N, tamanho:N:S ou estrutura:L)')


def por_tamanho(grupo, n, sob):
    raw, L = grupo['raw'], len(grupo['raw'])
    pedacos, ini = [], 0
    while ini < L:
        fim = min(ini + n, L)
        if fim < L and not raw[fim].isspace():
            j = fim
            while j > ini and not raw[j - 1].isspace():
                j -= 1
            if j > ini:
                fim = j
        a, b = ini, fim
        while a < b and raw[a].isspace():
            a += 1
        while b > a and raw[b - 1].isspace():
            b -= 1
        if b > a:
            k = a - 1
            while k >= 0 and raw[k] in ' \t':
                k -= 1
            meio = not (k < 0 or raw[k] == '\n' or raw[k] in '.!?')
            secs = [s for s in grupo['secoes'] if s['a'] < b and a < s['b']]
            pedacos.append({'id': f"{grupo['nome']}~{len(pedacos) + 1}", 'texto': raw[a:b],
                            'secoes': secs, 'meio': meio})
        if fim >= L:
            break
        nxt = fim - sob if sob else fim
        while sob and nxt < fim and nxt > 0 and not raw[nxt - 1].isspace():
            nxt += 1
        if nxt <= ini:
            nxt = fim
        ini = nxt
    return pedacos


def blocos_de(linhas):
    """Separa linhas em blocos: parágrafo, tabela ou lista."""
    blocos, atual = [], []
    for linha in linhas + ['']:
        if linha.strip():
            atual.append(linha)
            continue
        if atual:
            if all(x.startswith('|') for x in atual):
                tipo = 'tabela'
            elif all(re.match(r'(- |\d+\. )', x) for x in atual):
                tipo = 'lista'
            else:
                tipo = 'paragrafo'
            blocos.append((tipo, atual))
            atual = []
    return blocos


def juntar_ate(partes, sep, cabeca, espaco):
    """Junta partes em ordem enquanto cabem em espaco; cabeca (linhas da tabela) vai em todas."""
    saida, atual = [], []
    for p in partes:
        teste = sep.join(cabeca + atual + [p])
        if atual and len(teste) > espaco:
            saida.append(sep.join(cabeca + atual))
            atual = []
        atual.append(p)
    if atual:
        saida.append(sep.join(cabeca + atual))
    return saida


def cortar_bloco(tipo, linhas, espaco):
    """Devolve [(texto, começa_no_meio_da_frase)] com cada texto cabendo em espaco, se der."""
    if tipo == 'tabela' and len(linhas) > 2:
        return [(t, False) for t in juntar_ate(linhas[2:], '\n', linhas[:2], espaco)]
    if tipo in ('lista', 'tabela'):
        return [(t, False) for t in juntar_ate(linhas, '\n', [], espaco)]
    frases = re.split(r'(?<=[.!?])\s+', ' '.join(x.strip() for x in linhas))
    saida = []
    for f in frases:
        if len(f) <= espaco:
            saida.append((f, False))
        else:
            for i, t in enumerate(juntar_ate(f.split(), ' ', [], espaco)):
                saida.append((t, i > 0))
    junto, atual, meio_atual = [], [], False
    for t, meio in saida:
        if meio or (atual and len(' '.join(atual + [t])) > espaco):
            if atual:
                junto.append((' '.join(atual), meio_atual))
            atual, meio_atual = [], meio
        atual.append(t)
    if atual:
        junto.append((' '.join(atual), meio_atual))
    return junto


def por_estrutura(grupo, lim):
    pedacos = []
    for s in grupo['secoes']:
        subs, titulo_sub, linhas = [], None, []
        for linha in s['corpo'].splitlines():
            if linha.startswith('### '):
                if any(x.strip() for x in linhas) or titulo_sub:
                    subs.append((titulo_sub, linhas))
                titulo_sub, linhas = linha[4:].strip(), []
            else:
                linhas.append(linha)
        subs.append((titulo_sub, linhas))
        n = 0
        for titulo_sub, linhas in subs:
            cabeca = ' > '.join(s['caminho'] + ([titulo_sub] if titulo_sub else []))
            espaco = lim - len(cabeca) - 2
            atual = []

            def fecha(meio=False):
                nonlocal n, atual
                if atual:
                    n += 1
                    pedacos.append({'id': f"{s['id']}/{n}", 'texto': cabeca + '\n\n' + '\n\n'.join(atual),
                                    'secoes': [s], 'meio': meio})
                    atual = []

            for tipo, bl in blocos_de(linhas):
                texto = '\n'.join(bl)
                if len(texto) > espaco:
                    fecha()
                    for t, meio in cortar_bloco(tipo, bl, espaco):
                        atual = [t]
                        fecha(meio)
                elif atual and len('\n\n'.join(atual + [texto])) > espaco:
                    fecha()
                    atual = [texto]
                else:
                    atual.append(texto)
            fecha()
    return pedacos


def cortar(grupos, jeito):
    pedacos = []
    for g in grupos:
        if jeito['tipo'] == 'tamanho':
            pedacos += por_tamanho(g, jeito['n'], jeito['sob'])
        else:
            pedacos += por_estrutura(g, jeito['lim'])
    return pedacos


# ---------------------------------------------------------------- medidas

def onde_esta(pedacos, parte):
    alvo = junta(parte)
    return [p for p in pedacos if alvo in junta(p['texto'])]


def situacao(pedacos, q):
    achados = [onde_esta(pedacos, parte) for parte in q['precisa']]
    if any(not a for a in achados):
        return 'cortada'
    comuns = set(p['id'] for p in achados[0])
    for a in achados[1:]:
        comuns &= set(p['id'] for p in a)
    return 'inteira' if comuns else 'partida'


def medir(grupos, pedacos, perguntas):
    tam = [len(p['texto']) for p in pedacos]
    doc = sum(len(g['raw'].strip()) for g in grupos)
    return {
        'pedacos': len(pedacos), 'menor': min(tam), 'mediana': int(statistics.median(tam)), 'maior': max(tam),
        'palavras': max(len(p['texto'].split()) for p in pedacos),
        'indexado': sum(tam) / doc,
        'misturam': sum(1 for p in pedacos if len(p['secoes']) > 1),
        'meio': sum(1 for p in pedacos if p['meio']),
        'situacoes': {q['id']: situacao(pedacos, q) for q in perguntas} if perguntas else {},
    }


def virgula(x):
    return f'{x:.2f}'.replace('.', ',')


def campos_de(p):
    secs = p['secoes']
    if len(secs) == 1:
        s = secs[0]
        fim = s['fim'] or 'sem fim'
        return (f"trecho {s['id']}  versão {s['versao']}  vale [{s['inicio']}, {fim})  "
                f"lê: {', '.join(s['perfis'])}  {s['status']}")
    return f"mistura {len(secs)} seções: {', '.join(s['id'] for s in secs)}"


def mostrar_pedaco(p):
    print(f"pedaço {p['id']}  ({len(p['texto'])} caracteres)")
    print('  ' + campos_de(p))
    for linha in p['texto'].splitlines():
        partes = textwrap.wrap(linha, 86) or ['']
        for t in partes:
            print('  | ' + t if t else '  |')


# ---------------------------------------------------------------- comandos

def cmd_comparar(arquivo, jeitos, arq_perguntas):
    grupos = ler(arquivo)
    perguntas = ler_perguntas(arq_perguntas, grupos) if arq_perguntas else []
    jeitos = [ler_jeito(j) for j in jeitos]
    if not jeitos:
        raise Erro('diga pelo menos um jeito de cortar, por exemplo tamanho:500 ou estrutura:800')
    medidas = [(j['nome'], medir(grupos, cortar(grupos, j), perguntas)) for j in jeitos]
    w = max(18, max(len(n) for n, _ in medidas) + 2)
    print(f'{arquivo}: {sum(len(g["raw"].strip()) for g in grupos)} caracteres, '
          f'{sum(len(g["secoes"]) for g in grupos)} seções')
    cab = f"{'':<{w}}{'pedaços':>8}{'menor':>7}{'mediana':>9}{'maior':>7}{'palavras':>10}{'indexado':>10}" \
          f"{'misturam':>10}{'meio':>6}"
    if perguntas:
        cab += f"{'inteiras':>10}"
    print(cab)
    for nome, m in medidas:
        linha = f"{nome:<{w}}{m['pedacos']:>8}{m['menor']:>7}{m['mediana']:>9}{m['maior']:>7}{m['palavras']:>10}" \
                f"{virgula(m['indexado']) + 'x':>10}{m['misturam']:>10}{m['meio']:>6}"
        if perguntas:
            k = sum(1 for v in m['situacoes'].values() if v == 'inteira')
            linha += f"{f'{k} de {len(perguntas)}':>10}"
        print(linha)
    print('menor, mediana, maior: caracteres por pedaço. palavras: do maior pedaço.')
    print('indexado: texto dos pedaços dividido pelo texto do documento.')
    print('misturam: pedaços com mais de uma seção. meio: pedaços que começam no meio de uma frase.')
    if perguntas:
        print('inteiras: perguntas com tudo o que a resposta precisa dentro de um pedaço só.')
        print()
        cw = max(len(n) for n, _ in medidas) + 2
        print(f"{'pergunta':<10}" + ''.join(f'{n:>{cw}}' for n, _ in medidas))
        for q in perguntas:
            print(f"{q['id']:<10}" + ''.join(f"{m['situacoes'][q['id']]:>{cw}}" for _, m in medidas))
        print('partida: os textos da resposta estão inteiros, mas em pedaços diferentes.')
        print('cortada: algum texto da resposta foi cortado no meio e não está inteiro em pedaço nenhum.')


def cmd_listar(arquivo, jeito):
    grupos = ler(arquivo)
    j = ler_jeito(jeito)
    pedacos = cortar(grupos, j)
    print(f'{jeito} em {arquivo}: {len(pedacos)} pedaços')
    w = max(len(p['id']) for p in pedacos) + 2
    repetidas = set()
    for g in grupos:
        nomes = [s['secao'] for s in g['secoes']]
        repetidas |= {(g['nome'], n) for n in nomes if nomes.count(n) > 1}

    def rotulo(s):
        return f"{s['secao']} v{s['versao']}" if (s['documento'], s['secao']) in repetidas else s['secao']

    for p in pedacos:
        secs = ', '.join(rotulo(s) for s in p['secoes'])
        print(f"  {p['id']:<{w}}{len(p['texto']):>5}  {secs}")


def cmd_ver(arquivo, jeito, arq_perguntas, qid):
    grupos = ler(arquivo)
    perguntas = ler_perguntas(arq_perguntas, grupos)
    j = ler_jeito(jeito)
    qs = [q for q in perguntas if q['id'] == qid]
    if not qs:
        raise Erro(f'pergunta {qid} não está em {arq_perguntas}')
    q = qs[0]
    pedacos = cortar(grupos, j)
    print(f"{q['id']}: {q.get('pergunta', '')}")
    print(f"{jeito}: {situacao(pedacos, q)}")
    mostrar = []
    for i, parte in enumerate(q['precisa'], 1):
        achados = onde_esta(pedacos, parte)
        if achados:
            print(f"  texto {i} está em: {', '.join(p['id'] for p in achados)}")
        else:
            palavras = parte.split()
            comeco, final = ' '.join(palavras[:4]), ' '.join(palavras[-4:])
            achados = [p for p in pedacos if junta(comeco) in junta(p['texto'])
                       or junta(final) in junta(p['texto'])]
            print(f"  texto {i} foi cortado: o começo ou o fim dele está em {', '.join(p['id'] for p in achados)}")
        for p in achados:
            if p not in mostrar:
                mostrar.append(p)
    for p in mostrar:
        print()
        mostrar_pedaco(p)


def cmd_pedaco(arquivo, jeito, pid):
    pedacos = cortar(ler(arquivo), ler_jeito(jeito))
    achados = [p for p in pedacos if p['id'] == pid]
    if not achados:
        raise Erro(f'pedaço {pid} não existe com {jeito}; rode listar para ver os ids')
    mostrar_pedaco(achados[0])


def principal(argv):
    if not argv or argv[0] not in ('comparar', 'listar', 'ver'):
        raise Erro('use: cortar.py comparar|listar|ver ARQUIVO ... (veja o README da pasta)')
    cmd, resto = argv[0], argv[1:]
    perguntas = qid = pid = None
    soltos = []
    i = 0
    while i < len(resto):
        if resto[i] in ('--perguntas', '--pergunta', '--pedaco'):
            if i + 1 >= len(resto):
                raise Erro(f'{resto[i]} precisa de um valor')
            if resto[i] == '--perguntas':
                perguntas = resto[i + 1]
            elif resto[i] == '--pergunta':
                qid = resto[i + 1]
            else:
                pid = resto[i + 1]
            i += 2
        elif resto[i].startswith('--'):
            raise Erro(f'opção desconhecida: {resto[i]}')
        else:
            soltos.append(resto[i])
            i += 1
    if not soltos:
        raise Erro('falta o arquivo do documento')
    arquivo, jeitos = soltos[0], soltos[1:]
    if cmd == 'comparar':
        cmd_comparar(arquivo, jeitos, perguntas)
    elif cmd == 'listar':
        if len(jeitos) != 1:
            raise Erro('listar recebe um jeito de cortar, por exemplo estrutura:800')
        cmd_listar(arquivo, jeitos[0])
    elif len(jeitos) == 1 and pid and not qid:
        cmd_pedaco(arquivo, jeitos[0], pid)
    else:
        if len(jeitos) != 1 or not perguntas or not qid or pid:
            raise Erro('ver precisa de um jeito de cortar e de --pedaco ID, ou de --perguntas ARQUIVO e --pergunta ID')
        cmd_ver(arquivo, jeitos[0], perguntas, qid)


if __name__ == '__main__':
    try:
        principal(sys.argv[1:])
    except Erro as e:
        print(f'erro: {e}', file=sys.stderr)
        sys.exit(2)
