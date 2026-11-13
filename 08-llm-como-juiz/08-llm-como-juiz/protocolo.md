# Protocolo do juiz automático

Preencha uma cópia desse arquivo. Cada número vem da saída do `calibrar.py`; diga de qual comando.

## 1. O juiz

| Campo | O que vai aqui |
|---|---|
| Modelo avaliado (o assistente) e família | |
| Juiz e família | |
| Prompt do juiz | o arquivo e a data da última mudança |
| Regras que ele julga | |
| Rodadas por conversa | |
| Como o veredito sai | por exemplo: a maioria das rodadas |

## 2. As pessoas

| Campo | O que vai aqui |
|---|---|
| Quem marcou | duas pessoas, sem ver o juiz |
| Como sai o final | |
| Em quantos itens as duas concordaram | |

## 3. Calibração por regra

Uma linha por juiz e por regra. "Deixou passar" é quebra no final que o juiz marcou como cumpre.

| Juiz | Regra | Concorda | Quebras que pegou | Reprovou o que cumpre | Rodadas que não concordam |
|---|---|---|---|---|---|
| | | | | | |

## 4. Divergências anotadas

Uma linha por item da lista "divergências" do `calibrar.py`.

| Conversa | Regra | Pessoas | Final | Juiz (rodadas) | O que aconteceu | O que eu faço |
|---|---|---|---|---|---|---|
| | | | | | | |

## 5. Ordem nas comparações de duas respostas

| Juiz | Mesma escolha nas duas ordens | Nas que mudaram, ficou com a 1ª | Regra para quando muda |
|---|---|---|---|
| | | | |

## 6. Decisão

- O que o juiz decide sozinho:
- O que vai para uma pessoa:
- Quantas conversas por semana as pessoas continuam marcando, e como são escolhidas:
- Quando rodo a calibração de novo:
