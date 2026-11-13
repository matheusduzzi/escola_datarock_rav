# Ficha de memória e de precisão

Modelo: ______________________  Placa: ________ GB

## Parte 1. O que treina

| Caso | Conta por camada | Camadas | Parâmetros que treinam | Parte do total |
|---|---|---|---|---|
| LoRA `r = 8` em q e v | | | | |
| LoRA `r = 16` em q, k, v e o | | | | |

## Parte 2. A memória (pesos, gradientes e otimizador)

| Técnica | Modelo congelado | Adaptador e otimizador | Total | Cabe na placa? |
|---|---|---|---|---|
| Ajuste completo | | | | |
| LoRA, modelo em 16 bits | | | | |
| QLoRA, modelo em 4 bits | | | | |

## Parte 3. O diagrama

Desenhe uma barra por técnica, na mesma escala, com a linha da placa. Ou preencha a tabela abaixo, que tem a mesma informação.

| Técnica | Modelo guardado em | Cálculo em | Adaptador em | Otimizador em | Onde a precisão cai |
|---|---|---|---|---|---|
| Ajuste completo | | | | | |
| LoRA | | | | | |
| QLoRA | | | | | |

```text
 GB
  |
  |
  |
 8 +- - - - - - - - - - - - - - - - - - - -  placa
  |
  |
  0 +----------+----------+----------+
       completo     LoRA       QLoRA
```

## Parte 4. O modelo de 7 bilhões no notebook

| Medida do modelo em 4 bits | Modelo | Adaptador e otimizador | Total | Sobra na placa |
|---|---|---|---|---|
| pela conta da aula | | | | |
| pela medida do artigo | | | | |

O que eu faria antes de prometer:

## Parte 5. A frase do fornecedor

O que se sabe:

O que não se sabe:

Como descobrir na tarefa do tom:

## Parte 6. O que a ficha não conta
