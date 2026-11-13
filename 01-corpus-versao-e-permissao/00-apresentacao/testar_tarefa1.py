"""Testes da tarefa 1. Rode com: python3 testar_tarefa1.py"""
import copy
import sys

from tarefa1 import carregar, vigentes

TRECHOS = carregar()


def teste_antes_da_troca_de_versao():
    ids = vigentes(TRECHOS, 'cliente', '2026-09-30')
    assert 'trocas@1#prazo' in ids and 'trocas@2#prazo' not in ids, ids


def teste_dia_em_que_a_versao_nova_comeca():
    ids = vigentes(TRECHOS, 'cliente', '2026-10-01')
    assert 'trocas@2#prazo' in ids and 'trocas@1#prazo' not in ids, ids


def teste_rascunho_nunca_entra():
    ids = vigentes(TRECHOS, 'atendimento', '2026-12-15')
    assert 'trocas@3#prazo' not in ids and 'trocas@2#prazo' in ids, ids


def teste_perfil():
    cliente = vigentes(TRECHOS, 'cliente', '2026-11-05')
    supervisao = vigentes(TRECHOS, 'supervisao', '2026-11-05')
    assert not any(i.startswith(('excecoes@', 'financeiro@')) for i in cliente), cliente
    assert supervisao == ['excecoes@1#troca-fora-do-prazo'], supervisao


def teste_duas_versoes_valendo_no_mesmo_dia():
    dobrado = copy.deepcopy(TRECHOS)
    dobrado[0]['fim'] = None
    try:
        vigentes(dobrado, 'cliente', '2026-11-05')
    except ValueError:
        return
    raise AssertionError('duas versões de trocas#prazo valendo no mesmo dia precisam parar com ValueError')


def teste_lista_ordenada_e_entrada_intacta():
    antes = copy.deepcopy(TRECHOS)
    ids = vigentes(TRECHOS, 'cliente', '2026-11-05')
    assert ids == sorted(ids), ids
    assert TRECHOS == antes, 'a função alterou a lista recebida'


TESTES = [teste_antes_da_troca_de_versao, teste_dia_em_que_a_versao_nova_comeca, teste_rascunho_nunca_entra,
          teste_perfil, teste_duas_versoes_valendo_no_mesmo_dia, teste_lista_ordenada_e_entrada_intacta]

if __name__ == '__main__':
    falhas = 0
    for teste in TESTES:
        try:
            teste()
            print('ok   ', teste.__name__)
        except Exception as erro:  # o teste mostra qualquer erro, inclusive NotImplementedError
            falhas += 1
            print('FALHA', teste.__name__, '->', type(erro).__name__, erro)
    print(f'{len(TESTES) - falhas} de {len(TESTES)} testes passaram')
    sys.exit(1 if falhas else 0)
