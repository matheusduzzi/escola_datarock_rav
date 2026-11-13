# 11. Plano B e escalonamento

Os arquivos da aula. Rode os comandos de dentro dessa pasta. Só precisa do Python 3.9 ou mais novo, sem instalar nada. No Windows, troque `python3` por `py`.

| Arquivo | O que tem |
|---|---|
| `plano_b.py` | O plano B do assistente: as três paradas que decidem se ele responde, diz que não sabe ou passa para uma pessoa. |
| `conversas-semana.csv` | As 14 conversas da semana de 23 a 28 de novembro, usadas na aula. |
| `conversas-exercicio.csv` | As 10 conversas de 30 de novembro a 4 de dezembro, para o exercício. |
| `faq.json` | Duas perguntas frequentes do site da loja, que o assistente também lê. |
| `precedencia.py` | A regra de precedência do exercício, para você escrever. |
| `testar_precedencia.py` | Os testes dessa regra. |
| `meu-fluxo.md` | O modelo para as respostas do exercício. |

O plano B também lê as políticas em `../dados/politicas/politicas.json`.

## Comandos

```bash
python3 plano_b.py rodar --conversas conversas-semana.csv
python3 plano_b.py mostrar --conversas conversas-semana.csv S05
python3 testar_precedencia.py
python3 plano_b.py rodar --conversas conversas-exercicio.csv --precedencia
```

Antes de você escrever a regra, `testar_precedencia.py` termina com `0 de 6 testes passaram`, e o `--precedencia` para com `erro: a função politica_vence_faq ainda não foi escrita (precedencia.py)`. Isso é o esperado.

## As colunas das conversas

| Coluna | O que guarda |
|---|---|
| `id` | o número da conversa |
| `data` | o dia da conversa, no formato `AAAA-MM-DD` |
| `perfil` | quem pergunta: `cliente`, `atendimento`, `supervisao` ou `financeiro` |
| `pedido` | o número do pedido citado pelo cliente; vazio quando não tem |
| `pede_pessoa` | `sim` quando o cliente pediu para falar com uma pessoa |
| `pergunta` | a mensagem do cliente |
| `trechos` | os ids que a busca trouxe, separados por `\|` |
| `rascunho` | o que o modelo escreveu, com `[fonte: id]` no fim de cada frase |
| `confianca` | a nota de 0 a 1 que o modelo escreveu junto |

As conversas, os rascunhos e as notas foram escritos para o curso, do jeito que um assistente costuma responder. Nenhum modelo roda nessa pasta. Os sinais `pedido` e `pede_pessoa` já vêm anotados: o programa não tenta adivinhar isso do texto.

Se travar em algum comando, deixe um comentário na aula com o objetivo, o comando, a saída e o que você já tentou.
