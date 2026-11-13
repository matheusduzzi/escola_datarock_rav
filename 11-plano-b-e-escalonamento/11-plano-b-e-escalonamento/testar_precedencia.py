"""Testes da regra de precedência do exercício. Rode de dentro da pasta da aula:

    python3 testar_precedencia.py

Antes de você escrever a função, todos os testes mostram NotImplementedError.
"""
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from precedencia import politica_vence_faq  # noqa: E402
import plano_b  # noqa: E402

BASE = plano_b.ler_base()
# Dois trechos inventados só para o teste, que não existem nas políticas do kit.
EXTRA = dict(BASE)
EXTRA['campanha@1#frete'] = {'documento': 'campanha', 'secao': 'frete', 'texto': 'Frete grátis acima de R$ 99,00.'}
EXTRA['faq@2#frete'] = {'documento': 'faq', 'secao': 'frete', 'texto': 'Frete grátis acima de R$ 129,00.'}

TESTES = [
    ('política contra FAQ no frete: vale a política',
     ['entregas@1#frete', 'faq@1#frete'], BASE, 'entregas@1#frete'),
    ('a ordem do grupo não muda quem vence',
     ['faq@1#parcelamento', 'pagamentos@1#parcelamento'], BASE, 'pagamentos@1#parcelamento'),
    ('uma política contra dois textos do FAQ: vale a política',
     ['entregas@1#frete', 'faq@1#frete', 'faq@2#frete'], EXTRA, 'entregas@1#frete'),
    ('duas políticas brigando: ninguém vence',
     ['campanha@1#frete', 'entregas@1#frete'], EXTRA, None),
    ('duas políticas e o FAQ: ninguém vence',
     ['campanha@1#frete', 'entregas@1#frete', 'faq@1#frete'], EXTRA, None),
    ('só textos do FAQ brigando: ninguém vence',
     ['faq@1#frete', 'faq@2#frete'], EXTRA, None),
]

passaram = 0
for nome, grupo, base, esperado in TESTES:
    try:
        veio = politica_vence_faq(list(grupo), base)
        if veio == esperado:
            passaram += 1
            print(f'ok     {nome}')
        else:
            print(f'FALHOU {nome}: esperava {esperado}, veio {veio}')
    except Exception as e:  # noqa: BLE001
        print(f'FALHOU {nome}: {type(e).__name__}')
        if not isinstance(e, NotImplementedError):
            traceback.print_exc(limit=1)
print(f'{passaram} de {len(TESTES)} testes passaram')
sys.exit(0 if passaram == len(TESTES) else 1)
