"""A regra de precedência que a coordenadora decidiu, para o exercício da aula.

Quando uma política da loja e o FAQ do site dizem coisas diferentes sobre o mesmo assunto,
vale a política, e o FAQ entra na lista de correção. Se duas políticas brigam, ou se o
conflito é só entre textos do FAQ, ninguém vence: a conversa vai para uma pessoa.

O plano B chama essa função com o grupo de ids em conflito e a base inteira:

    python3 plano_b.py rodar --conversas conversas-exercicio.csv --precedencia

Para testar:

    python3 testar_precedencia.py
"""


def politica_vence_faq(grupo, base):
    """Recebe a lista de ids em conflito (todos valem no dia e para o perfil da conversa) e a
    base, um dicionário id -> trecho, em que cada trecho tem o campo 'documento'. O FAQ do site
    tem documento 'faq'.

    Devolve o id que vale, ou None quando a conversa deve ir para uma pessoa.
    """
    raise NotImplementedError
