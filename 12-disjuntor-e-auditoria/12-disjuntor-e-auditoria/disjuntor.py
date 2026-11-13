"""Disjuntor e auditoria: simula uma tarde do assistente com uma parada e investiga o que ficou anotado.

O assistente atende cada conversa em três partes: a busca traz os trechos das políticas, o modelo
escreve o rascunho e a checagem do plano B (aula 11) decide se o rascunho sai. O simulador roda a
tarde com três jeitos de tentar de novo:

  hoje       repete tudo: até 3 buscas, até 9 chamadas ao modelo por rascunho (3 da integração
             vezes 3 da biblioteca) e até 3 rascunhos quando o rascunho não serve.
  limite     repete só o que pode passar sozinho: 2 buscas e 2 chamadas ao modelo no máximo,
             com 2 segundos de espera, e um segundo rascunho só quando a checagem barrou uma frase.
  disjuntor  o limite, mais um disjuntor na busca e outro no modelo. Depois de N falhas seguidas
             o disjuntor abre e as conversas seguintes nem chamam aquela parte. Passado o tempo
             aberto, uma conversa testa; se der certo, ele fecha.

Cada chamada vira uma linha na auditoria, com a parte (busca, modelo, checagem), a tentativa,
o resultado e a duração. O comando investigar lê só a auditoria.

    python3 disjuntor.py comparar --conversas conversas-dia.csv --incidentes incidentes-dia.csv
    python3 disjuntor.py simular --politica disjuntor --conversas conversas-dia.csv --incidentes incidentes-dia.csv
    python3 disjuntor.py investigar --auditoria auditoria-disjuntor.csv
    python3 disjuntor.py investigar --auditoria auditoria-disjuntor.csv --conversa D18

Só biblioteca padrão, Python 3.9 ou mais novo.
"""
import argparse
import csv
import heapq
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PARTES = ('busca', 'modelo')
ASSUNTOS = ('trocas', 'entregas', 'pagamentos', 'garantia', 'outros')
RASCUNHOS = ('ok', 'nao-achei', 'conflito', 'barrado:numero-fora-do-trecho', 'barrado:frase-sem-fonte')
EFEITOS = {'busca': ('fora', 'indice-antigo'), 'modelo': ('fora', 'prompt-novo')}

# Quanto cada chamada demora, em segundos. A falha do modelo é o timeout de 20 s da integração.
DURACAO = {('busca', 'ok'): 1, ('busca', 'nada-que-vale'): 1, ('busca', 'erro'): 5,
           ('modelo', 'ok'): 4, ('modelo', 'erro'): 20}

# Tentativas contam a primeira chamada. rascunhos = quantos rascunhos no máximo por conversa.
POLITICAS = {
    'hoje': {'busca_erro': 3, 'busca_vazia': 3, 'modelo_erro': 9, 'rascunhos': 3, 'espera': 1,
             'repete_rascunho': ('barrado', 'nao-achei'), 'disjuntor': False},
    'limite': {'busca_erro': 2, 'busca_vazia': 1, 'modelo_erro': 2, 'rascunhos': 2, 'espera': 2,
               'repete_rascunho': ('barrado',), 'disjuntor': False},
    'disjuntor': {'busca_erro': 2, 'busca_vazia': 1, 'modelo_erro': 2, 'rascunhos': 2, 'espera': 2,
                  'repete_rascunho': ('barrado',), 'disjuntor': True},
}
ACOES = ('responder', 'não sei', 'passar')
COLUNAS_AUDITORIA = ('hora', 'conversa', 'assunto', 'parte', 'tentativa', 'resultado', 'detalhe', 'duracao_s')


class Erro(Exception):
    pass


def segundos(hora, onde):
    try:
        h, m, s = (int(x) for x in hora.split(':'))
        if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60):
            raise ValueError
    except ValueError:
        raise Erro(f'{onde}: hora "{hora}" fora do formato HH:MM:SS')
    return h * 3600 + m * 60 + s


def falhas(n):
    return '1 falha' if n == 1 else f'{n} falhas seguidas'


def relogio(t):
    return f'{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}'


def ler_csv(caminho, colunas):
    try:
        with open(caminho, newline='', encoding='utf-8') as f:
            leitor = csv.DictReader(f)
            faltam = [c for c in colunas if c not in (leitor.fieldnames or [])]
            if faltam:
                raise Erro(f'{caminho}: falta a coluna {", ".join(faltam)}')
            return [{k: (v or '').strip() for k, v in l.items()} for l in leitor]
    except FileNotFoundError:
        raise Erro(f'não achei o arquivo {caminho}')


def ler_conversas(caminho):
    conversas, vistos = [], set()
    for l in ler_csv(caminho, ('id', 'hora', 'assunto', 'pedido', 'pede_pessoa', 'rascunhos')):
        cid = l['id']
        if not cid:
            raise Erro(f'{caminho}: conversa sem id')
        if cid in vistos:
            raise Erro(f'{caminho}: o id {cid} aparece duas vezes')
        vistos.add(cid)
        if l['assunto'] not in ASSUNTOS:
            raise Erro(f'{caminho}, {cid}: assunto "{l["assunto"]}" não existe ({", ".join(ASSUNTOS)})')
        if l['pede_pessoa'] not in ('sim', 'nao'):
            raise Erro(f'{caminho}, {cid}: pede_pessoa precisa ser sim ou nao, veio "{l["pede_pessoa"]}"')
        rascunhos = [r.strip() for r in l['rascunhos'].split('|') if r.strip()]
        if not rascunhos:
            raise Erro(f'{caminho}, {cid}: sem rascunho; o roteiro precisa dizer o que o modelo escreve')
        for r in rascunhos:
            if r not in RASCUNHOS:
                raise Erro(f'{caminho}, {cid}: rascunho "{r}" não existe ({", ".join(RASCUNHOS)})')
        conversas.append({'id': cid, 't': segundos(l['hora'], f'{caminho}, {cid}'), 'assunto': l['assunto'],
                          'pedido': l['pedido'], 'pede_pessoa': l['pede_pessoa'] == 'sim',
                          'rascunhos': rascunhos})
    if not conversas:
        raise Erro(f'{caminho}: nenhuma conversa')
    return sorted(conversas, key=lambda c: (c['t'], c['id']))


def ler_incidentes(caminho):
    incidentes = []
    for n, l in enumerate(ler_csv(caminho, ('parte', 'inicio', 'fim', 'efeito', 'assunto')), 2):
        onde = f'{caminho}, linha {n}'
        if l['parte'] not in EFEITOS:
            raise Erro(f'{onde}: parte "{l["parte"]}" não existe ({", ".join(EFEITOS)})')
        if l['efeito'] not in EFEITOS[l['parte']]:
            raise Erro(f'{onde}: efeito "{l["efeito"]}" não existe para {l["parte"]} ({", ".join(EFEITOS[l["parte"]])})')
        if l['assunto'] and l['assunto'] not in ASSUNTOS:
            raise Erro(f'{onde}: assunto "{l["assunto"]}" não existe')
        ini, fim = segundos(l['inicio'], onde), segundos(l['fim'], onde)
        if fim <= ini:
            raise Erro(f'{onde}: o fim ({l["fim"]}) precisa vir depois do início ({l["inicio"]})')
        incidentes.append({'parte': l['parte'], 'ini': ini, 'fim': fim, 'efeito': l['efeito'],
                           'assunto': l['assunto']})
    return incidentes


def efeito(incidentes, parte, t, assunto):
    for i in incidentes:
        if i['parte'] == parte and i['ini'] <= t < i['fim'] and (not i['assunto'] or i['assunto'] == assunto):
            return i['efeito']
    return None


def mundo(parte, t, conversa, n_rascunho, incidentes):
    """O que a chamada devolve, pela hora em que ela começa. Só o roteiro de incidentes sabe disso."""
    e = efeito(incidentes, parte, t, conversa['assunto'])
    if e == 'fora':
        return 'erro', 'timeout' if parte == 'modelo' else 'erro do serviço de busca'
    if parte == 'busca':
        return ('nada-que-vale', 'só voltaram trechos vencidos') if e == 'indice-antigo' else ('ok', '')
    lista = conversa['rascunhos']
    rascunho = lista[min(n_rascunho, len(lista)) - 1]
    if e == 'prompt-novo' and rascunho != 'conflito':
        rascunho = 'barrado:numero-fora-do-trecho'
    return 'ok', rascunho


class Disjuntor:
    """Fechado: deixa chamar e conta falhas seguidas. Aberto: ninguém chama até passar o tempo.
    Meio-aberto: uma conversa testa; deu certo, fecha; falhou, abre de novo."""

    def __init__(self, parte, abrir_apos, aberto_s, anotar):
        self.parte, self.abrir_apos, self.aberto_s, self.anotar = parte, abrir_apos, aberto_s, anotar
        self.estado, self.falhas, self.reabre, self.testando = 'fechado', 0, None, False
        self.aberturas = []

    def pode_chamar(self, t):
        """Devolve (pode, é_teste)."""
        if self.estado == 'aberto' and t >= self.reabre:
            self.estado = 'meio-aberto'
            self.anotar(t, '-', '', self.parte, '-', 'disjuntor meio-aberto', 'a próxima chamada testa', 0)
        if self.estado == 'fechado':
            return True, False
        if self.estado == 'meio-aberto' and not self.testando:
            self.testando = True
            return True, True
        return False, False

    def resultado(self, t, ok, teste):
        if teste:
            self.testando = False
            if ok:
                self.estado, self.falhas = 'fechado', 0
                self.anotar(t, '-', '', self.parte, '-', 'disjuntor fechou', 'o teste deu certo', 0)
            else:
                self._abrir(t, 'o teste falhou')
            return
        if self.estado != 'fechado':
            return  # chamada que começou antes de abrir: não muda o estado
        if ok:
            self.falhas = 0
            return
        self.falhas += 1
        if self.falhas >= self.abrir_apos:
            self._abrir(t, falhas(self.falhas))

    def _abrir(self, t, porque):
        self.estado, self.reabre, self.falhas = 'aberto', t + self.aberto_s, 0
        self.aberturas.append(t)
        self.anotar(t, '-', '', self.parte, '-', 'disjuntor abriu', f'{porque}; fica aberto {self.aberto_s} s', 0)


def atender(c, pol):
    """Uma conversa, do jeito da política. Pede chamadas ao simulador com yield e recebe o resultado."""
    motivos = []

    # Busca.
    erros = vazias = tentativa = 0
    while True:
        tentativa += 1
        res, _ = yield ('chamar', 'busca', str(tentativa), 0)
        if res == 'erro':
            erros += 1
            if erros < pol['busca_erro']:
                yield ('esperar', pol['espera'])
                continue
        elif res == 'nada-que-vale':
            vazias += 1
            if vazias < pol['busca_vazia']:
                continue
        break
    if res in ('erro', 'nao-chamada'):
        motivos.append('busca-fora')
    elif res == 'nada-que-vale':
        motivos.append('busca-vazia')

    # Modelo e checagem, um rascunho por vez.
    rascunho = None
    n = 0
    while not motivos:
        n += 1
        erros = tentativa = 0
        while True:
            tentativa += 1
            res, rascunho = yield ('chamar', 'modelo', f'{n}.{tentativa}', n)
            if res == 'erro':
                erros += 1
                if erros < pol['modelo_erro']:
                    yield ('esperar', pol['espera'])
                    continue
            break
        if res != 'ok':
            motivos.append('modelo-fora')
            break
        tipo = rascunho.split(':')[0]
        if tipo == 'ok':
            yield ('anotar', 'checagem', str(n), 'passou', '')
            break
        if tipo == 'conflito':
            yield ('anotar', 'checagem', str(n), 'conflito', 'duas fontes que valem dizem coisas diferentes')
            motivos.append('conflito')
            break
        detalhe = rascunho.split(':')[1] if tipo == 'barrado' else 'o modelo disse que não achou'
        yield ('anotar', 'checagem', str(n), 'barrou' if tipo == 'barrado' else 'nao-achou', detalhe)
        if tipo in pol['repete_rascunho'] and n < pol['rascunhos']:
            continue
        motivos.append(detalhe if tipo == 'barrado' else 'modelo-nao-achou')

    # Quem resolve (aula 11): conflito, cliente que pediu, não sei com pedido vão para uma pessoa.
    if not motivos:
        acao = 'responder'
    else:
        acao = 'passar' if 'conflito' in motivos else 'não sei'
    if c['pede_pessoa']:
        motivos.append('pediu-pessoa')
        acao = 'passar'
    elif acao == 'não sei' and c['pedido']:
        motivos.append('nao-sei-com-pedido')
        acao = 'passar'
    yield ('fim', acao, ' + '.join(motivos) or '-')


def simular(conversas, incidentes, politica, abrir_apos=3, aberto_s=300):
    """Roda todas as conversas ao mesmo tempo, na ordem das horas. Devolve as linhas da auditoria e as
    contas que só o simulador sabe (o que estava fora de verdade)."""
    if politica not in POLITICAS:
        raise Erro(f'política "{politica}" não existe ({", ".join(POLITICAS)})')
    if abrir_apos < 1 or aberto_s < 1:
        raise Erro('--abrir-apos e --aberto precisam ser 1 ou mais')
    pol = POLITICAS[politica]
    linhas = []
    seq = [0]

    def anotar(t, conversa, assunto, parte, tentativa, resultado, detalhe, duracao):
        seq[0] += 1
        linhas.append((t, seq[0], {'hora': relogio(t), 'conversa': conversa, 'assunto': assunto, 'parte': parte,
                                   'tentativa': tentativa, 'resultado': resultado, 'detalhe': detalhe,
                                   'duracao_s': str(duracao)}))

    disjuntores = {p: Disjuntor(p, abrir_apos, aberto_s, anotar) for p in PARTES} if pol['disjuntor'] else {}
    agenda, n = [], 0

    def agendar(t, tipo, c, g, carga=None):
        nonlocal n
        n += 1
        heapq.heappush(agenda, (t, n, tipo, c['id'], c, g, carga))

    for c in conversas:
        agendar(c['t'], 'seguir', c, atender(c, pol))
    sem_parte_no_ar = 0
    while agenda:
        t, _, tipo, _, c, g, carga = heapq.heappop(agenda)
        envio = None
        if tipo == 'concluir':
            parte, tentativa, res, detalhe, teste, inicio = carga
            if parte in disjuntores:
                # Só falha técnica conta. Busca sem trecho que vale é resposta, não queda.
                disjuntores[parte].resultado(t, res != 'erro', teste)
            anotar(inicio, c['id'], c['assunto'], parte, tentativa, res,
                   detalhe if (parte == 'busca' or res != 'ok') else '', t - inicio)
            envio = (res, detalhe)
        while True:
            try:
                pedido = g.send(envio)
            except StopIteration:
                break
            envio = None
            if pedido[0] == 'esperar':
                agendar(t + pedido[1], 'retomar', c, g)
                break
            if pedido[0] == 'anotar':
                _, parte, tentativa, res, detalhe = pedido
                anotar(t, c['id'], c['assunto'], parte, tentativa, res, detalhe, 0)
                envio = True
                continue
            if pedido[0] == 'fim':
                _, acao, motivos = pedido
                anotar(t, c['id'], c['assunto'], 'conversa', '-', acao, motivos, t - c['t'])
                break
            _, parte, tentativa, n_rascunho = pedido
            teste = False
            if parte in disjuntores:
                pode, teste = disjuntores[parte].pode_chamar(t)
                if not pode:
                    if efeito(incidentes, parte, t, c['assunto']) != 'fora':
                        sem_parte_no_ar += 1
                    anotar(t, c['id'], c['assunto'], parte, tentativa, 'nao-chamada', 'disjuntor aberto', 0)
                    envio = ('nao-chamada', 'disjuntor aberto')
                    continue
            res, detalhe = mundo(parte, t, c, n_rascunho, incidentes)
            agendar(t + DURACAO[(parte, 'erro' if res == 'erro' else 'ok')], 'concluir', c, g,
                    (parte, tentativa, res, detalhe, teste, t))
            break
    linhas.sort(key=lambda x: (x[0], x[1]))
    return [l for _, _, l in linhas], {'sem_parte_no_ar': sem_parte_no_ar,
                                       'aberturas': {p: d.aberturas for p, d in disjuntores.items()}}


def resumo(linhas, extra):
    conversas = [l for l in linhas if l['parte'] == 'conversa']
    chamadas = {p: [l for l in linhas if l['parte'] == p and l['resultado'] != 'nao-chamada'
                    and l['tentativa'] != '-'] for p in PARTES}
    esperas = [int(l['duracao_s']) for l in conversas]
    r = {'conversas': len(conversas),
         'acoes': {a: sum(1 for l in conversas if l['resultado'] == a) for a in ACOES},
         'busca': len(chamadas['busca']),
         'busca_erro': sum(1 for l in chamadas['busca'] if l['resultado'] == 'erro'),
         'modelo': len(chamadas['modelo']),
         'modelo_erro': sum(1 for l in chamadas['modelo'] if l['resultado'] == 'erro'),
         'nao_chamadas': sum(1 for l in linhas if l['resultado'] == 'nao-chamada'),
         'rascunhos': sum(1 for l in linhas if l['parte'] == 'checagem'),
         'espera_max': max(esperas), 'espera_30': sum(1 for e in esperas if e > 30),
         'espera_total': sum(esperas), 'sem_parte_no_ar': extra['sem_parte_no_ar'],
         'aberturas': sum(len(v) for v in extra['aberturas'].values())}
    return r


def gravar(linhas, caminho):
    with open(caminho, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS_AUDITORIA)
        w.writeheader()
        w.writerows(linhas)


def mostrar_resumo(politica, r, abrir_apos, aberto_s, extra):
    titulo = f'política {politica}'
    if POLITICAS[politica]['disjuntor']:
        titulo += f' (abre depois de {falhas(abrir_apos)}, fica aberto {aberto_s} s)'
    print(titulo)
    print(f'  conversas: {r["conversas"]}')
    print('  ações: ' + ', '.join(f'{a} {r["acoes"][a]}' for a in ACOES))
    print(f'  chamadas à busca: {r["busca"]} ({r["busca_erro"]} com erro)')
    print(f'  chamadas ao modelo: {r["modelo"]} ({r["modelo_erro"]} com erro)')
    print(f'  rascunhos checados: {r["rascunhos"]}')
    if POLITICAS[politica]['disjuntor']:
        print(f'  chamadas que o disjuntor não deixou fazer: {r["nao_chamadas"]}'
              f' ({r["sem_parte_no_ar"]} com a parte já no ar)')
        for p in PARTES:
            horas = ', '.join(relogio(t) for t in extra['aberturas'][p]) or 'não abriu'
            print(f'  disjuntor {"da" if p == "busca" else "do"} {p}, abriu em: {horas}')
    print(f'  espera do cliente: maior {r["espera_max"]} s; conversas que esperaram mais de 30 s: {r["espera_30"]}')


def comparar(conversas, incidentes, abrir_apos, aberto_s):
    rs = {}
    for p in POLITICAS:
        linhas, extra = simular(conversas, incidentes, p, abrir_apos, aberto_s)
        rs[p] = resumo(linhas, extra)
    print(f'{"":<44}' + ''.join(f'{p:>11}' for p in POLITICAS))
    linhas_tabela = [
        ('responder', lambda r: r['acoes']['responder']),
        ('não sei', lambda r: r['acoes']['não sei']),
        ('passar', lambda r: r['acoes']['passar']),
        ('chamadas à busca', lambda r: r['busca']),
        ('chamadas ao modelo', lambda r: r['modelo']),
        ('  com erro', lambda r: r['modelo_erro']),
        ('rascunhos checados', lambda r: r['rascunhos']),
        ('chamadas que o disjuntor não deixou fazer', lambda r: r['nao_chamadas']),
        ('  com a parte já no ar', lambda r: r['sem_parte_no_ar']),
        ('maior espera do cliente (s)', lambda r: r['espera_max']),
        ('conversas que esperaram mais de 30 s', lambda r: r['espera_30']),
    ]
    for nome, f in linhas_tabela:
        print(f'{nome:<44}' + ''.join(f'{f(rs[p]):>11}' for p in POLITICAS))
    print()
    print(f'{rs["hoje"]["conversas"]} conversas; disjuntor: abre depois de {falhas(abrir_apos)}, '
          f'fica aberto {aberto_s} s')


# Investigação: só a auditoria.

def ler_auditoria(caminho):
    linhas = ler_csv(caminho, COLUNAS_AUDITORIA)
    if not linhas:
        raise Erro(f'{caminho}: auditoria vazia')
    for n, l in enumerate(linhas, 2):
        segundos(l['hora'], f'{caminho}, linha {n}')
        if l['parte'] not in ('busca', 'modelo', 'checagem', 'conversa'):
            raise Erro(f'{caminho}, linha {n}: parte "{l["parte"]}" não existe')
        if not l['duracao_s'].isdigit():
            raise Erro(f'{caminho}, linha {n}: duração "{l["duracao_s"]}" não é número de segundos')
    return linhas


FALHAS = [('busca', 'erro'), ('busca', 'nada-que-vale'), ('busca', 'nao-chamada'),
          ('modelo', 'erro'), ('modelo', 'nao-chamada'), ('checagem', 'barrou'),
          ('checagem', 'nao-achou'), ('checagem', 'conflito')]


def investigar(linhas, janela_min=5):
    conversas = [l for l in linhas if l['parte'] == 'conversa']
    print(f'auditoria: {len(linhas)} linhas, {len(conversas)} conversas, '
          f'de {linhas[0]["hora"]} a {linhas[-1]["hora"]}')
    print()
    print('falhas por parte')
    print(f'  {"parte":<9}{"resultado":<15}{"vezes":>6}{"conversas":>11}   primeira  última    assuntos')
    for parte, res in FALHAS:
        ls = [l for l in linhas if l['parte'] == parte and l['resultado'] == res]
        if not ls:
            continue
        assuntos = {}
        for l in ls:
            assuntos[l['assunto']] = assuntos.get(l['assunto'], 0) + 1
        conv = len({l['conversa'] for l in ls})
        txt = ', '.join(f'{a} {n}' for a, n in sorted(assuntos.items(), key=lambda x: (-x[1], x[0])))
        print(f'  {parte:<9}{res:<15}{len(ls):>6}{conv:>11}   {ls[0]["hora"]}  {ls[-1]["hora"]}  {txt}')
    detalhes = {}
    for l in linhas:
        if l['parte'] == 'checagem' and l['resultado'] == 'barrou':
            detalhes[l['detalhe']] = detalhes.get(l['detalhe'], 0) + 1
    if detalhes:
        print('  barrou por: ' + ', '.join(f'{d} {n}' for d, n in sorted(detalhes.items())))
    estados = [l for l in linhas if l['resultado'].startswith('disjuntor')]
    print()
    print('disjuntor')
    if not estados:
        print('  nenhuma mudança de estado')
    for l in estados:
        print(f'  {l["hora"]}  {l["parte"]:<7} {l["resultado"][len("disjuntor "):]:<12} {l["detalhe"]}')
    print()
    print(f'de {janela_min} em {janela_min} minutos')
    cab = ['conversas', 'busca erro', 'busca vazia', 'modelo erro', 'não chamou', 'barrou',
           'responder', 'não sei', 'passar']
    print(f'  {"início":<8}' + ''.join(f'{c:>12}' for c in cab))
    ini = segundos(linhas[0]['hora'], '') // (janela_min * 60) * janela_min * 60
    fim = segundos(linhas[-1]['hora'], '')
    t = ini
    while t <= fim:
        js = [l for l in linhas if t <= segundos(l['hora'], '') < t + janela_min * 60]

        def conta(parte, res):
            return sum(1 for l in js if l['parte'] == parte and l['resultado'] == res)
        valores = [conta('conversa', a) for a in ACOES]
        linha = [sum(valores), conta('busca', 'erro'), conta('busca', 'nada-que-vale'), conta('modelo', 'erro'),
                 sum(1 for l in js if l['resultado'] == 'nao-chamada'), conta('checagem', 'barrou'), *valores]
        print(f'  {relogio(t)[:5]:<8}' + ''.join(f'{v:>12}' for v in linha))
        t += janela_min * 60
    print()
    print('motivos do não sei e do passar')
    motivos = {}
    for l in conversas:
        for m in l['detalhe'].split(' + '):
            if m != '-':
                motivos.setdefault(m, []).append(l['conversa'])
    for m, ids in sorted(motivos.items(), key=lambda x: (-len(x[1]), x[0])):
        print(f'  {m:<24}{len(ids):>3}   {" ".join(ids)}')


def mostrar_conversa(linhas, cid):
    ls = [l for l in linhas if l['conversa'] == cid]
    if not ls:
        raise Erro(f'a conversa {cid} não está na auditoria')
    print(f'{cid}  {ls[0]["assunto"]}')
    print(f'  {"hora":<9}{"parte":<10}{"tentativa":<11}{"resultado":<14}{"duração":>8}  detalhe')
    for l in ls:
        print(f'  {l["hora"]:<9}{l["parte"]:<10}{l["tentativa"]:<11}{l["resultado"]:<14}{l["duracao_s"] + " s":>8}'
              f'  {l["detalhe"]}'.rstrip())


def main(argv=None):
    p = argparse.ArgumentParser(description='Disjuntor e auditoria: simular a tarde e investigar a auditoria.')
    sub = p.add_subparsers(dest='comando')
    for nome, ajuda in (('simular', 'roda a tarde com uma política e grava a auditoria'),
                        ('comparar', 'roda a tarde com as três políticas e mostra lado a lado')):
        s = sub.add_parser(nome, help=ajuda)
        s.add_argument('--conversas', required=True)
        s.add_argument('--incidentes', required=True)
        s.add_argument('--abrir-apos', type=int, default=3, help='falhas seguidas para abrir (padrão 3)')
        s.add_argument('--aberto', type=int, default=300, help='segundos aberto antes do teste (padrão 300)')
        if nome == 'simular':
            s.add_argument('--politica', required=True, choices=list(POLITICAS))
            s.add_argument('--auditoria', help='arquivo da auditoria (padrão auditoria-<política>.csv)')
    s = sub.add_parser('investigar', help='lê a auditoria e agrupa as falhas por parte e por horário')
    s.add_argument('--auditoria', required=True)
    s.add_argument('--conversa', help='mostra só uma conversa, linha por linha')
    s.add_argument('--janela', type=int, default=5, help='minutos de cada linha do horário (padrão 5)')
    a = p.parse_args(argv)
    if not a.comando:
        p.print_help()
        return 2
    try:
        if a.comando == 'investigar':
            if a.janela < 1:
                raise Erro('--janela precisa ser 1 ou mais')
            linhas = ler_auditoria(a.auditoria)
            if a.conversa:
                mostrar_conversa(linhas, a.conversa)
            else:
                investigar(linhas, a.janela)
            return 0
        conversas = ler_conversas(a.conversas)
        incidentes = ler_incidentes(a.incidentes)
        if a.comando == 'comparar':
            comparar(conversas, incidentes, a.abrir_apos, a.aberto)
            return 0
        linhas, extra = simular(conversas, incidentes, a.politica, a.abrir_apos, a.aberto)
        saida = a.auditoria or f'auditoria-{a.politica}.csv'
        gravar(linhas, saida)
        mostrar_resumo(a.politica, resumo(linhas, extra), a.abrir_apos, a.aberto, extra)
        print(f'auditoria gravada em {saida} ({len(linhas)} linhas)')
    except Erro as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
