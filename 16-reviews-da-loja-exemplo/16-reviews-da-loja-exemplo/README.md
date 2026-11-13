# 16. Reviews da Loja Exemplo

Os arquivos da aula «Reviews da Loja Exemplo»: as avaliações de produtos que os clientes deixaram, o guia de motivos, a regra de palavras-chave de hoje, os registros das abordagens e o programa que compara tudo.

## O que tem aqui

| Arquivo | O que é |
|---|---|
| `guia-motivos.md` | o guia de 16/11/2026: os seis motivos, a ordem quando há dois e o que fazer com negação e ironia |
| `avaliacao.csv` | as 60 avaliações da semana, com o rótulo de cada uma das duas pessoas (`rotulo_a`, `rotulo_b`) e o gabarito (`motivo`) |
| `desenvolvimento.csv` | 29 avaliações rotuladas, usadas para escrever o guia |
| `avaliacoes-rotuladas.csv` | 153 avaliações rotuladas, de onde saem os exemplos e o treino do ajuste |
| `palavras-chave.json` | a regra de palavras-chave que o TI montou em 2025 |
| `abordagens.json` | o que vai no pedido de cada abordagem, o modelo e o que ela precisa para montar |
| `precos.json` | os preços da proposta, por milhão de tokens, e o custo de rotular e treinar |
| `regra.json` | a regra de 16/11/2026, escrita antes do teste |
| `registro-palavras.csv` | a saída do `reviews.py palavras` nas 60 avaliações |
| `registro-modelos.csv` | o registro das quatro abordagens com modelo |
| `registro-exercicio.csv`, `registro-exercicio-2.csv` | os dois registros do fornecedor, para o exercício |
| `decisao.md` | o modelo da escolha que você entrega |
| `reviews.py` | o programa. Só usa a biblioteca padrão do Python 3.9 ou mais novo |

Rode tudo de dentro dessa pasta. No Windows, troque `python3` por `py`.

O `registro-modelos.csv` e os registros do exercício foram escritos para o curso: nenhum modelo rodou para gerar o motivo previsto. Os exemplos da abordagem `recuperados` são a saída da busca de verdade. Os preços também são do caso. Para usar o seu modelo, gere um registro com as mesmas colunas e passe no `--registro`.

## Os comandos da aula

```bash
python3 reviews.py palavras --conjunto avaliacao.csv --saida meu-registro-palavras.csv
python3 reviews.py palavras --conjunto avaliacao.csv --mostrar A06
python3 reviews.py exemplos --id A13 --conjunto avaliacao.csv
python3 reviews.py avaliar --conjunto avaliacao.csv --registro registro-palavras.csv --registro registro-modelos.csv
```

O exercício começa com um comando que termina em `erro:` de propósito.

## O formato do registro

Uma linha por avaliação e abordagem:

| Coluna | O que guarda |
|---|---|
| `abordagem` | o nome, igual a uma chave de `abordagens.json` |
| `id` | o id da avaliação |
| `motivo` | o motivo que a abordagem respondeu. Fora da lista conta como erro e aparece na linha "fora da lista" |
| `tokens_entrada`, `tokens_saida` | os tokens do pedido e da resposta |
| `exemplos` | os ids dos exemplos que foram no pedido, separados por espaço. Só podem vir de `avaliacoes-rotuladas.csv` |

Quando um arquivo tem problema, o `reviews.py` para com uma linha `erro:` e código 2, sem gravar nada. Por exemplo: uma avaliação que falta ou aparece duas vezes, uma avaliação de fora do conjunto, tokens negativos, ou um exemplo que vem do próprio conjunto de avaliação.

## Se precisar de ajuda

Deixe um comentário na aula. Conte o objetivo, o comando, a saída e o que já tentou, sem dados pessoais.
