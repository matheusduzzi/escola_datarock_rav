# 10. Alucinação e incerteza

Os arquivos da aula «Alucinação e incerteza». Tudo roda com o Python 3.9 ou mais novo, só com a biblioteca padrão, de dentro dessa pasta.

## O que tem aqui

| Arquivo | Para que serve |
|---|---|
| `falhas.py` | Mostra cada resposta com o texto dos trechos que o assistente leu e responde a primeira pergunta da aula (os trechos bastam?). Com a sua classificação da resposta, dá o nome da falha e onde mexer. |
| `respostas-semana.csv` | As 12 respostas da semana que a aula classifica. |
| `classificacao-semana.csv` | A minha classificação dessas 12 respostas, com a frase que decidiu. |
| `respostas-exercicio.csv` | As 10 respostas do exercício. |
| `minha-classificacao.csv` | Onde você anota a classificação das respostas do exercício. |
| `taxonomia.md` | O modelo da taxonomia que você entrega no exercício. |

As respostas dos dois arquivos foram escritas para o curso, do jeito que um assistente costuma responder. Os trechos são os de `../dados/politicas/politicas.json`.

## Os comandos da aula

```bash
python3 falhas.py mostrar --respostas respostas-semana.csv
python3 falhas.py mostrar --respostas respostas-semana.csv C05
python3 falhas.py resumir --respostas respostas-semana.csv --classificacao classificacao-semana.csv
```

## Como ler um arquivo de respostas

Cada linha é uma resposta do assistente. As colunas são `id`, `data` (o dia da pergunta, `AAAA-MM-DD`), `perfil` (quem perguntou), `pergunta`, `esperado` (o trecho que responde, do conjunto de referência; vazio quando a loja não tem regra; dois trechos separados por `|` quando a resposta precisa dos dois), `trechos` (os 3 que a busca trouxe, separados por `|`), `resposta` e `confianca` (a nota de 0 a 1 que o próprio modelo escreveu).

No arquivo de classificação, a coluna `resposta` aceita `apoiada`, `contradiz`, `acrescenta` ou `nao-sei`. A coluna `frase` é para você: o programa não lê.

## Quando o programa para

O `falhas.py` para com `erro:` e código 2 quando:

- falta uma coluna, um id está vazio ou repetido, a data está fora do formato ou o perfil não existe;
- a pergunta ou a resposta está vazia, ou a linha não tem trechos;
- um trecho não existe nas políticas, ou o esperado não vale para aquele perfil naquele dia;
- a confiança não é um número de 0 a 1;
- a classificação tem um id que não está nas respostas, classifica um id duas vezes, deixa alguma resposta sem classificar ou usa uma palavra fora das quatro.

Antes de você classificar, o `resumir` do exercício para e diz qual resposta falta. É o esperado.

## Se precisar de ajuda

Deixe um comentário na aula. Conte o objetivo, o comando que você rodou, a saída que apareceu e o que já tentou, sem dados pessoais.
