"""Tarefa 1 do diagnóstico: que trechos o assistente pode usar num dia, para um perfil."""
import json
from pathlib import Path

POLITICAS = Path(__file__).resolve().parent.parent / 'dados' / 'politicas' / 'politicas.json'


def carregar():
    return json.loads(POLITICAS.read_text(encoding='utf-8'))


def vigentes(trechos, perfil, dia):
    """Retorna a lista ordenada dos ids que o perfil pode ler no dia (texto 'AAAA-MM-DD').

    Escreva aqui a sua função. As regras estão na tarefa 1 do diagnóstico.
    """
    raise NotImplementedError('escreva a função vigentes')


if __name__ == '__main__':
    trechos = carregar()
    print('trechos no arquivo:', len(trechos))
    for dia in ('2026-09-30', '2026-10-01'):
        ids = vigentes(trechos, 'cliente', dia)
        prazo = [i for i in ids if i.startswith('trocas@') and i.endswith('#prazo')]
        print(f'{dia} cliente: {len(ids)} trechos; prazo de troca: {", ".join(prazo)}')
