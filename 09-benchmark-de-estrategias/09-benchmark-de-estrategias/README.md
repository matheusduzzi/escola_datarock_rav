# 09. Benchmark de estratégias

Os arquivos da aula «Benchmark de estratégias». Tudo roda com o Python 3.9 ou mais novo, só com a biblioteca padrão, de dentro dessa pasta.

## O que tem aqui

| Arquivo | Para que serve |
|---|---|
| `benchmark.py` | Compara estratégias no mesmo conjunto: qualidade por tipo, tempo (p50 e p95) e custo, e aplica a regra escrita antes do teste. Tem dois modos: `busca` e `agente`. |
| `lexical.py` | O BM25 da aula 04, sem mudança. |
| `rodar_bm25.py` | Roda o BM25 em todas as perguntas do conjunto e grava o registro, com o tempo medido no seu computador. |
| `conjunto-avaliacao.csv` | As 16 perguntas da busca: 4 de termo exato, 4 de paráfrase, 4 de número e 4 sem resposta. |
| `registro-bm25.csv` | O registro do BM25 que eu gravei com `rodar_bm25.py`. |
| `registro-fornecedor.csv` | O registro que o fornecedor mandou: busca por significado, híbrida e híbrida com reranker, nas mesmas 16 perguntas. |
| `regra-busca.json` | A regra da compra, escrita antes do teste. |
| `precos.json` | Os preços da proposta e dos dois modelos do assistente. São inventados para o curso. |
| `tarefas-agente.csv`, `registro-agente.csv`, `regra-agente.json` | As 12 tarefas do assistente rodadas com o modelo grande e com o pequeno. |
| `tarefas-exercicio.csv`, `registro-exercicio.csv`, `regra-exercicio.json` | O exercício: o assistente com e sem a skill de prazos. |
| `decisao.md` | O modelo da nota de decisão que você entrega no exercício. |

## Os comandos da aula

```bash
python3 benchmark.py busca --conjunto conjunto-avaliacao.csv --registro registro-bm25.csv --registro registro-fornecedor.csv --regra regra-busca.json
python3 benchmark.py agente --conjunto tarefas-agente.csv --registro registro-agente.csv --regra regra-agente.json
```

Para gravar o seu próprio registro do BM25:

```bash
python3 rodar_bm25.py --conjunto conjunto-avaliacao.csv --saida meu-registro-bm25.csv
```

Os trechos de cada pergunta saem iguais aos de `registro-bm25.csv`. O tempo sai outro, porque é o do seu computador.

## Como ler um registro

Cada linha é uma pergunta (ou tarefa) rodada numa estratégia (ou versão).

Na busca, as colunas são `estrategia`, `id`, `ranking` (os 3 primeiros trechos, separados por `|`; vazio quando a busca não trouxe nada), `tempo_ms`, `tokens_embedding` (tokens que a pergunta gastou no modelo de embeddings) e `pares_reranker` (quantos pares de pergunta e trecho o reranker leu).

No agente, as colunas são `versao`, `id`, `modelo`, `aprovada` (`sim` ou `nao`, pela rubrica da aula 07), `passos` (chamadas ao modelo na tarefa), `tokens_entrada`, `tokens_saida` e `tempo_ms`.

## Quando o programa para

O `benchmark.py` para com `erro:` e código 2 quando:

- uma estratégia não rodou alguma pergunta do conjunto, rodou uma pergunta duas vezes ou rodou uma pergunta que não está no conjunto;
- um ranking traz um trecho que o perfil não pode ler na data da regra;
- falta uma coluna, um número está vazio ou negativo, ou `aprovada` não é `sim` nem `nao`;
- a regra cita uma estratégia ou um tipo de pergunta que não existe.

Com `--descartar-fora-do-conjunto`, ele tira as linhas de perguntas que não estão no conjunto, diz quais tirou e segue. Pergunta do conjunto que faltou continua parando o programa.

O registro do exercício para de propósito na primeira vez que você roda. O enunciado diz o que fazer.

## Se precisar de ajuda

Deixe um comentário na aula. Conte o objetivo, o comando que você rodou, a saída que apareceu e o que já tentou, sem dados pessoais.
