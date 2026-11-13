"""Separar os exemplos do ajuste, ler o registro do treino e comparar respostas.

Só biblioteca padrão. Rode de dentro da pasta 15-ajuste-com-qlora:

    python3 ajuste.py separar --exemplos exemplos.jsonl --saida separado
    python3 ajuste.py registro --registro ajuste-ti/registro-treino.csv
    python3 ajuste.py comparar --avaliacao separado/avaliacao.jsonl --treino separado/treino.jsonl \
        --respostas respostas/base.jsonl --respostas respostas/qlora-passo-22.jsonl

O treinar_qlora.py e o responder.py usam as funções mensagens() e carregar_politicas() daqui,
para o treino e a resposta montarem o pedido do mesmo jeito que o comparar mede.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

AQUI = Path(__file__).resolve().parent
POLITICAS = AQUI.parent / 'dados' / 'politicas' / 'politicas.json'
PROMPTS = AQUI / 'prompts'
PARTE_AVALIACAO = 0.2
PARTE_VALIDACAO = 0.1
PALAVRAS_CURTO = 50
FORMULAS = ('prezado', 'prezada', 'informamos', 'atenciosamente', 'agradecemos o contato',
            'agradecemos o seu contato', 'venho por meio', 'permanecemos a disposicao',
            'estamos a disposicao', 'solicitamos', 'cordialmente')
NAO_SEI = 'nao sei'
ROTULO = {'treino': 'treino', 'validacao': 'validação', 'avaliacao': 'avaliação'}


class Erro(Exception):
    """Problema nos arquivos: o programa para com código 2 e não grava nada."""


# ---------- leitura ----------

def ler_jsonl(caminho):
    caminho = Path(caminho)
    if not caminho.is_file():
        raise Erro(f'não achei o arquivo {caminho}')
    linhas = []
    for n, linha in enumerate(caminho.read_text(encoding='utf-8').splitlines(), 1):
        if not linha.strip():
            continue
        try:
            linhas.append(json.loads(linha))
        except json.JSONDecodeError as e:
            raise Erro(f'{caminho.name}, linha {n}: JSON inválido ({e.msg})')
    return linhas


def gravar_jsonl(caminho, linhas):
    texto = ''.join(json.dumps(l, ensure_ascii=False) + '\n' for l in linhas)
    Path(caminho).write_text(texto, encoding='utf-8')


def carregar_politicas(caminho=POLITICAS):
    caminho = Path(caminho)
    if not caminho.is_file():
        raise Erro(f'não achei as políticas em {caminho}')
    return {t['id']: t for t in json.loads(caminho.read_text(encoding='utf-8'))}


def carregar_prompt(nome):
    arquivo = PROMPTS / f'{nome}.txt'
    if not arquivo.is_file():
        raise Erro(f'prompt desconhecido: {nome} (não achei {arquivo.name} em prompts/)')
    return arquivo.read_text(encoding='utf-8').strip()


CAMPOS = ('id', 'conversa', 'data', 'cliente', 'assunto', 'pergunta', 'trechos', 'resposta')


def validar_exemplo(ex, arquivo, politicas):
    faltam = [c for c in CAMPOS if c not in ex or ex[c] in (None, '') and c != 'trechos']
    if faltam:
        raise Erro(f'{arquivo}: exemplo {ex.get("id", "sem id")} sem {", ".join(faltam)}')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(ex['data'])):
        raise Erro(f'{arquivo}: exemplo {ex["id"]} com data fora do formato AAAA-MM-DD: {ex["data"]}')
    if not isinstance(ex['trechos'], list):
        raise Erro(f'{arquivo}: exemplo {ex["id"]}: trechos precisa ser uma lista')
    desconhecidos = [t for t in ex['trechos'] if t not in politicas]
    if desconhecidos:
        raise Erro(f'{arquivo}: exemplo {ex["id"]} cita trecho que não existe: {", ".join(desconhecidos)}')


# ---------- regras ----------

def normalizar(texto):
    sem_acento = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
    return ' '.join(re.sub(r'[^a-z0-9 ]', ' ', sem_acento.lower()).split())


def numeros(texto):
    """Números do texto como valor: 'R$ 199,00' e '199' são o mesmo número."""
    achados = set()
    for bruto in re.findall(r'\d+(?:[.,]\d+)*', texto):
        limpo = bruto
        if ',' in limpo:
            limpo = limpo.replace('.', '').replace(',', '.')
        elif re.fullmatch(r'\d{1,3}(\.\d{3})+', limpo):
            limpo = limpo.replace('.', '')
        try:
            achados.add(Decimal(limpo).normalize())
        except InvalidOperation:
            continue
    return achados


def vale_no_dia(trecho, dia, perfil='cliente'):
    return (trecho['status'] == 'aprovado' and perfil in trecho['perfis'] and trecho['inicio'] <= dia
            and (trecho['fim'] is None or dia < trecho['fim']))


def numeros_fora(ex, politicas):
    permitidos = numeros(ex['pergunta'])
    for t in ex['trechos']:
        permitidos |= numeros(politicas[t]['texto'])
    return sorted(numeros(ex['resposta']) - permitidos)


def fmt_num(n):
    return format(n, 'f').replace('.', ',')


def ordem(conversa):
    """Posição da conversa no sorteio: o hash do id, igual em qualquer computador."""
    return hashlib.sha256(conversa.encode('utf-8')).hexdigest()


# ---------- separar ----------

def descartar(exemplos, politicas, fixos=None):
    """Retorna (bons, descartados). Cada descarte tem o motivo e o detalhe.

    fixos: {'avaliacao': [...], 'validacao': [...]} de uma separação anterior. Exemplo novo de uma
    conversa desses arquivos, ou com a mesma pergunta, sai, para eles continuarem iguais.
    """
    bons, fora, vistos = [], [], {}
    perguntas_fixas, conversas_fixas = {}, {}
    for nome, linhas in (fixos or {}).items():
        for ex in linhas:
            perguntas_fixas[normalizar(ex['pergunta'])] = (nome, ex['id'])
            conversas_fixas[ex['conversa']] = nome
            vistos[(normalizar(ex['pergunta']), normalizar(ex['resposta']))] = ex['id']
    for ex in exemplos:
        chave = (normalizar(ex['pergunta']), normalizar(ex['resposta']))
        nao_vale = [t for t in ex['trechos'] if not vale_no_dia(politicas[t], ex['data'])]
        fora_do_trecho = numeros_fora(ex, politicas)
        if chave in vistos:
            fora.append((ex, 'repetido', f'igual a {vistos[chave]}'))
        elif nao_vale:
            fora.append((ex, 'trecho-nao-vale', f'{", ".join(nao_vale)} não vale em {ex["data"]}'))
        elif fora_do_trecho:
            fora.append((ex, 'numero-fora-do-trecho',
                         f'{", ".join(fmt_num(n) for n in fora_do_trecho)} não está nos trechos nem na pergunta'))
        elif ex['conversa'] in conversas_fixas:
            nome = conversas_fixas[ex['conversa']]
            fora.append((ex, f'conversa-da-{nome}', f'a conversa {ex["conversa"]} está na {ROTULO[nome]}'))
        elif normalizar(ex['pergunta']) in perguntas_fixas:
            nome, outro = perguntas_fixas[normalizar(ex['pergunta'])]
            fora.append((ex, f'pergunta-da-{nome}', f'mesma pergunta de {outro}, na {ROTULO[nome]}'))
        else:
            vistos[chave] = ex['id']
            bons.append(ex)
    return bons, fora


def assunto_da_conversa(exemplos):
    por_conversa = {}
    for ex in exemplos:
        por_conversa.setdefault(ex['conversa'], ex['assunto'])
    return por_conversa


def sortear(conversas_por_assunto):
    """Por assunto, as conversas na ordem do hash: as primeiras vão para a avaliação, as seguintes para a validação."""
    lado = {}
    for assunto, conversas in conversas_por_assunto.items():
        fila = sorted(conversas, key=ordem)
        n_aval = max(1, round(PARTE_AVALIACAO * len(fila)))
        n_val = max(1, round(PARTE_VALIDACAO * len(fila)))
        if n_aval + n_val >= len(fila):
            raise Erro(f'assunto {assunto} tem só {len(fila)} conversas: não dá para separar treino, validação e avaliação')
        for i, c in enumerate(fila):
            lado[c] = 'avaliacao' if i < n_aval else 'validacao' if i < n_aval + n_val else 'treino'
    return lado


def cmd_separar(a):
    politicas = carregar_politicas(a.politicas)
    exemplos = []
    for arq in a.exemplos:
        for ex in ler_jsonl(arq):
            validar_exemplo(ex, Path(arq).name, politicas)
            exemplos.append(ex)
    ids = [ex['id'] for ex in exemplos]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        raise Erro(f'id repetido nos exemplos: {", ".join(repetidos)}')
    lidos, n_conv = len(exemplos), len({ex['conversa'] for ex in exemplos})
    mantida = None
    if a.manter:
        pasta = Path(a.manter)
        mantida = {nome: ler_jsonl(pasta / f'{nome}.jsonl') for nome in ('treino', 'validacao', 'avaliacao')}
    fixos = {k: mantida[k] for k in ('avaliacao', 'validacao')} if mantida else None
    if mantida:
        # O treino anterior entra de novo pelo arquivo de exemplos; aqui só valem os fixos.
        faltam = [ex['id'] for ex in mantida['treino'] if ex['id'] not in set(ids)]
        if faltam:
            raise Erro(f'{len(faltam)} exemplos do treino anterior não estão em --exemplos: '
                       'passe também o arquivo da primeira separação')
        ids_fixos = {ex['id'] for linhas in fixos.values() for ex in linhas}
        exemplos = [ex for ex in exemplos if ex['id'] not in ids_fixos]
    bons, fora = descartar(exemplos, politicas, fixos)

    if mantida:
        arquivos = {'treino': list(bons), 'validacao': list(mantida['validacao']),
                    'avaliacao': list(mantida['avaliacao'])}
    else:
        conversas = {}
        for c, assunto in assunto_da_conversa(bons).items():
            conversas.setdefault(assunto, []).append(c)
        lado = sortear(conversas)
        arquivos = {'treino': [], 'validacao': [], 'avaliacao': []}
        for ex in bons:
            arquivos[lado[ex['conversa']]].append(ex)

    # Garantias da separação.
    onde = {}
    for nome, linhas in arquivos.items():
        for ex in linhas:
            onde.setdefault(ex['conversa'], set()).add(nome)
    em_dois = sorted(c for c, s in onde.items() if len(s) > 1)
    if em_dois:
        raise Erro(f'conversa em dois arquivos: {", ".join(em_dois)}')
    perg_treino = {normalizar(ex['pergunta']) for ex in arquivos['treino'] + arquivos['validacao']}
    vazou = [ex['id'] for ex in arquivos['avaliacao'] if normalizar(ex['pergunta']) in perg_treino]
    if vazou:
        raise Erro(f'pergunta da avaliação também no treino ou na validação: {", ".join(vazou)}')

    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    for nome, linhas in arquivos.items():
        gravar_jsonl(saida / f'{nome}.jsonl', linhas)

    print(f'exemplos lidos: {lidos} em {n_conv} conversas')
    print(f'descartados: {len(fora)}')
    for ex, motivo, detalhe in fora:
        print(f'  {ex["id"]:<7} {motivo:<23} {detalhe}')
    print()
    assuntos = sorted({ex['assunto'] for ex in bons} | {ex['assunto'] for ex in arquivos['avaliacao']})
    print(f'{"conversas por assunto":<24}{"treino":>8}{"validação":>11}{"avaliação":>11}')
    por = {nome: {} for nome in arquivos}
    for nome, linhas in arquivos.items():
        for c in {ex['conversa'] for ex in linhas}:
            assunto = next(ex['assunto'] for ex in linhas if ex['conversa'] == c)
            por[nome][assunto] = por[nome].get(assunto, 0) + 1
    for s in assuntos:
        print(f'  {s:<22}{por["treino"].get(s, 0):>8}{por["validacao"].get(s, 0):>11}{por["avaliacao"].get(s, 0):>11}')
    print(f'{"exemplos":<24}{len(arquivos["treino"]):>8}{len(arquivos["validacao"]):>11}{len(arquivos["avaliacao"]):>11}')
    sem = {nome: sum(1 for ex in linhas if not ex['trechos']) for nome, linhas in arquivos.items()}
    print(f'{"  sem trecho":<24}{sem["treino"]:>8}{sem["validacao"]:>11}{sem["avaliacao"]:>11}')
    print()
    if mantida:
        print(f'validação e avaliação mantidas de {a.manter}: {len(arquivos["validacao"])} e '
              f'{len(arquivos["avaliacao"])} exemplos, sem mudança; o que é novo foi para o treino')
    print(f'gravados: {saida}/treino.jsonl, {saida}/validacao.jsonl, {saida}/avaliacao.jsonl')
    print('nenhuma conversa em dois arquivos; nenhuma pergunta da avaliação no treino ou na validação')


# ---------- registro ----------

def num(texto):
    texto = (texto or '').strip()
    return float(texto) if texto else None


def cmd_registro(a):
    arq = Path(a.registro)
    if not arq.is_file():
        raise Erro(f'não achei o arquivo {arq}')
    with arq.open(encoding='utf-8', newline='') as f:
        linhas = list(csv.DictReader(f))
    faltam = {'passo', 'epoca', 'loss_treino', 'loss_validacao', 'checkpoint'} - set(linhas[0] if linhas else [])
    if faltam:
        raise Erro(f'{arq.name} sem as colunas: {", ".join(sorted(faltam))}')
    print(f'{"passo":>6}{"época":>7}{"loss treino":>13}{"loss validação":>16}  checkpoint')
    avaliadas = []
    for l in linhas:
        lt, lv = num(l['loss_treino']), num(l['loss_validacao'])
        print(f'{l["passo"]:>6}{l["epoca"]:>7}{fmt(lt):>13}{fmt(lv):>16}  {l["checkpoint"] or "-"}')
        if lv is not None:
            avaliadas.append((lv, l))
    if not avaliadas:
        raise Erro('o registro não tem loss de validação: não dá para escolher o checkpoint')
    melhor_lv, melhor = min(avaliadas, key=lambda x: x[0])
    print()
    print(f'menor loss de validação: {fmt(melhor_lv)} no passo {melhor["passo"]} ({melhor["checkpoint"] or "sem checkpoint salvo"})')
    depois = [lv for lv, l in avaliadas if int(l['passo']) > int(melhor['passo'])]
    if depois:
        subidas = sum(1 for x, y in zip([melhor_lv] + depois, depois) if y > x)
        primeira, ultima = linhas[0], linhas[-1]
        print(f'depois dele: validação subiu em {subidas} de {len(depois)} avaliações; '
              f'treino foi de {fmt(num(primeira["loss_treino"]))} a {fmt(num(ultima["loss_treino"]))}')


def fmt(x):
    return '-' if x is None else f'{x:.2f}'.replace('.', ',')


# ---------- comparar ----------

def mensagens(ex, politicas, prompt):
    """O pedido que o modelo recebe: o prompt do sistema e a pergunta com os trechos."""
    if ex['trechos']:
        trechos = '\n'.join(f'- [{t}] {politicas[t]["texto"]}' for t in ex['trechos'])
    else:
        trechos = '- nenhum trecho para essa pergunta'
    usuario = f'Cliente: {ex["cliente"]}\nData: {ex["data"]}\nPergunta: {ex["pergunta"]}\nTrechos:\n{trechos}'
    return [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': usuario}]


def avaliar(ex, resposta, politicas):
    norm = normalizar(resposta)
    disse_nao_sei = NAO_SEI in norm
    fora = numeros_fora(dict(ex, resposta=resposta), politicas)
    sem_trecho = not ex['trechos']
    fiel = not fora and (disse_nao_sei if sem_trecho else True)
    palavras = len(resposta.split())
    primeiro_nome = normalizar(ex['cliente']).split()[0]
    formula = [f for f in FORMULAS if f in norm]
    r = {
        'fiel': fiel, 'fora': fora, 'nao_sei': disse_nao_sei, 'sem_trecho': sem_trecho,
        'curto': palavras <= PALAVRAS_CURTO, 'palavras': palavras,
        'nome': primeiro_nome in norm.split(), 'formula': formula,
    }
    r['tom'] = r['curto'] and r['nome'] and not formula
    r['passou'] = r['fiel'] and r['tom']
    return r


def cmd_comparar(a):
    politicas = carregar_politicas(a.politicas)
    avaliacao = ler_jsonl(a.avaliacao)
    treino = ler_jsonl(a.treino)
    for ex in avaliacao + treino:
        validar_exemplo(ex, 'avaliação/treino', politicas)
    ids_aval = [ex['id'] for ex in avaliacao]
    conv_treino = {ex['conversa'] for ex in treino}
    perg_treino = {normalizar(ex['pergunta']) for ex in treino}
    vazou = [ex['id'] for ex in avaliacao if ex['conversa'] in conv_treino or normalizar(ex['pergunta']) in perg_treino]
    if vazou:
        raise Erro(f'a avaliação tem conversa ou pergunta do treino: {", ".join(vazou)}. Separe de novo antes de comparar')
    ids_treino = {ex['id'] for ex in treino}

    variantes = []
    for arq in a.respostas:
        linhas = ler_jsonl(arq)
        nome = Path(arq).stem
        ids = [l.get('id') for l in linhas]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        faltam = [i for i in ids_aval if i not in ids]
        sobram = [i for i in ids if i not in ids_aval]
        if dup:
            raise Erro(f'{nome}: pergunta respondida duas vezes: {", ".join(dup)}')
        if sobram:
            do_treino = [i for i in sobram if i in ids_treino]
            extra = f'; {len(do_treino)} delas estão no treino' if do_treino else ''
            raise Erro(f'{nome}: responde {len(sobram)} perguntas que não estão na avaliação{extra}')
        if faltam:
            raise Erro(f'{nome}: faltam {len(faltam)} perguntas da avaliação: {", ".join(faltam)}')
        prompts = {l.get('prompt') for l in linhas}
        if len(prompts) != 1:
            raise Erro(f'{nome}: as respostas usam prompts diferentes: {", ".join(sorted(map(str, prompts)))}')
        prompt_nome = prompts.pop()
        prompt = carregar_prompt(prompt_nome)
        por_id = {l['id']: l for l in linhas}
        res = {}
        entrada = 0
        for ex in avaliacao:
            res[ex['id']] = avaliar(ex, por_id[ex['id']]['resposta'], politicas)
            entrada += sum(len(m['content']) for m in mensagens(ex, politicas, prompt))
        variantes.append((nome, prompt_nome, res, round(entrada / len(avaliacao))))

    n = len(avaliacao)
    com = [ex['id'] for ex in avaliacao if ex['trechos']]
    sem = [ex['id'] for ex in avaliacao if not ex['trechos']]
    print(f'avaliação: {n} perguntas ({len(com)} com trecho, {len(sem)} sem trecho)')
    larg = max(14, *(len(v[0]) + 2 for v in variantes))
    print(f'{"":<28}' + ''.join(f'{v[0]:>{larg}}' for v in variantes))

    def linha(rotulo, ids, chave, valor=True):
        celulas = []
        for _, _, res, _ in variantes:
            ok = sum(1 for i in ids if res[i][chave] == valor)
            celulas.append(f'{ok}/{len(ids)}')
        print(f'{rotulo:<28}' + ''.join(f'{c:>{larg}}' for c in celulas))

    print(f'{"prompt":<28}' + ''.join(f'{v[1]:>{larg}}' for v in variantes))
    linha('fiel ao trecho', ids_aval, 'fiel')
    if sem:
        linha('"não sei" sem trecho', sem, 'nao_sei')
    linha('"não sei" com trecho', com, 'nao_sei')
    linha(f'curto (até {PALAVRAS_CURTO} palavras)', ids_aval, 'curto')
    linha('chama pelo nome', ids_aval, 'nome')
    sem_formula = [f'{sum(1 for i in ids_aval if not res[i]["formula"])}/{n}' for _, _, res, _ in variantes]
    print(f'{"sem fórmula de carta":<28}' + ''.join(f'{c:>{larg}}' for c in sem_formula))
    linha('tom (as três)', ids_aval, 'tom')
    linha('passou (fiel e tom)', ids_aval, 'passou')
    print(f'{"entrada média (caracteres)":<28}' + ''.join(f'{v[3]:>{larg}}' for v in variantes))
    print()
    print('o que não passou')
    for nome, _, res, _ in variantes:
        for i in ids_aval:
            r = res[i]
            motivos = []
            if r['fora']:
                motivos.append('número fora do trecho: ' + ', '.join(fmt_num(x) for x in r['fora']))
            if r['sem_trecho'] and not r['nao_sei']:
                motivos.append('respondeu sem trecho')
            if not r['curto']:
                motivos.append(f'{r["palavras"]} palavras')
            if not r['nome']:
                motivos.append('sem o nome')
            if r['formula']:
                motivos.append('fórmula: ' + ', '.join(r['formula']))
            if motivos:
                print(f'  {nome:<{larg - 2}} {i:<7} {"; ".join(motivos)}')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='comando', required=True)
    s = sub.add_parser('separar', help='separa os exemplos em treino, validação e avaliação')
    s.add_argument('--exemplos', action='append', required=True, help='arquivo .jsonl; pode repetir')
    s.add_argument('--saida', required=True, help='pasta onde gravar treino, validação e avaliação')
    s.add_argument('--manter', help='pasta de uma separação anterior: validação e avaliação ficam como estão')
    s.add_argument('--politicas', default=str(POLITICAS))
    r = sub.add_parser('registro', help='lê o registro do treino e aponta o checkpoint')
    r.add_argument('--registro', required=True)
    c = sub.add_parser('comparar', help='compara respostas no conjunto de avaliação')
    c.add_argument('--avaliacao', required=True)
    c.add_argument('--treino', required=True)
    c.add_argument('--respostas', action='append', required=True, help='arquivo .jsonl; pode repetir')
    c.add_argument('--politicas', default=str(POLITICAS))
    a = p.parse_args(argv)
    try:
        {'separar': cmd_separar, 'registro': cmd_registro, 'comparar': cmd_comparar}[a.comando](a)
    except Erro as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
