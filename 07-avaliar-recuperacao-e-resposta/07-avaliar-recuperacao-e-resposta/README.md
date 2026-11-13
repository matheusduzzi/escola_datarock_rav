# 07. Avaliar recuperação e resposta

Os arquivos da aula. Rode os comandos de dentro dessa pasta. O programa lê as políticas em `dados/politicas/politicas.json`, na raiz do kit, e só usa a biblioteca padrão do Python 3.9 ou mais novo. No Windows, troque `python3` por `py`.

| Arquivo | O que é |
|---|---|
| `rubrica.py` | Mede a busca e a resposta em separado, pergunta por pergunta, e diz onde cada uma falhou. |
| `dev.csv` | As 15 perguntas de desenvolvimento, do jeito que o `separar` da aula 06 gravou. |
| `registro-k3.csv` | O que o assistente fez com três trechos por pergunta: o ranking, a resposta e a marcação `certa`. |
| `julgamento-k3.csv` | As respostas do `registro-k3.csv` quebradas em afirmações, com o trecho de apoio de cada uma. |
| `registro-k1.csv` | O registro do exercício: o mesmo assistente com um trecho só por pergunta. |
| `julgamento-k1.csv` | O julgamento do exercício, sem as três perguntas que você julga. |
| `ficha-rubrica.md` | O modelo da ficha que você entrega no exercício. |

Os rankings dos registros saíram do `lexical.py` da aula 04, com o perfil e a data de cada pergunta. As respostas e a coluna `certa` foram escritas para o curso: nenhum modelo de linguagem rodou para gerar essas linhas. Quando você tiver o seu assistente, gere um registro no mesmo formato e rode a mesma rubrica.

## As colunas

| Arquivo | Coluna | O que vai nela |
|---|---|---|
| registro | `id` | o id da pergunta no `dev.csv` |
| registro | `ranking` | os ids dos trechos que a busca passou ao modelo, na ordem, separados por `\|`. Vazio quando a busca não trouxe nada |
| registro | `resposta` | o que o assistente respondeu |
| registro | `certa` | `sim` ou `nao`, marcado por quem comparou a resposta com a resposta esperada |
| julgamento | `id` | o id da pergunta. Uma linha por afirmação, então o mesmo id se repete |
| julgamento | `afirmacao` | uma coisa que a resposta afirma, curta |
| julgamento | `apoio` | o id do trecho que diz aquilo, `nenhum` quando nenhum trecho diz, ou `recusa` na frase em que o assistente diz que não sabe |

## Comandos

```bash
python3 rubrica.py dev.csv registro-k3.csv julgamento-k3.csv
python3 rubrica.py dev.csv registro-k3.csv julgamento-k3.csv --detalhe c06
python3 rubrica.py dev.csv registro-k1.csv julgamento-k1.csv
```

| Parte | Como o programa conta | Passa quando |
|---|---|---|
| relevância | trechos do ranking que estão em `esperados`, do total que veio. Não conta nas sem resposta | não reprova sozinha |
| cobertura | trechos de `esperados` que vieram no ranking, do total esperado | todos vieram |
| fidelidade | afirmações com apoio, do total. Apoio fora do ranking não conta. Número da afirmação que não está no trecho de apoio também não conta | todas têm apoio |
| certa | a coluna `certa` do registro | `sim` |
| sem resposta | alguma afirmação com apoio `recusa` | recusou e nada sem apoio |

O `--detalhe` mostra o ranking, a resposta e cada afirmação de uma pergunta, depois do resumo.

## Quando o programa para

Com um arquivo errado, o programa lista os problemas e sai com código 2, sem mostrar nota:

- coluna faltando ou arquivo vazio;
- pergunta do conjunto sem linha no registro ou sem afirmação no julgamento;
- id do registro ou do julgamento que não está no conjunto, ou pergunta repetida no registro;
- trecho do ranking que não existe, que aparece duas vezes ou que não passa no filtro de perfil e data da pergunta;
- `certa` diferente de `sim` e `nao`, ou resposta vazia;
- afirmação vazia, apoio vazio ou apoio que não existe nas políticas.

Quando o arquivo está certo, mas algo merece um olho, a linha começa com `atenção:` e o programa continua. Por exemplo: o apoio aponta um trecho que não veio na busca, ou um número da afirmação não está no trecho.

## Se precisar de ajuda

Deixe um comentário na aula. Conte o objetivo, o comando que você rodou, a saída que apareceu e o que já tentou, sem dados pessoais.
