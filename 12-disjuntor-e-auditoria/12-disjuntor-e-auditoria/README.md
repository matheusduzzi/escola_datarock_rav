# 12. Disjuntor e auditoria

Os arquivos da aula «Disjuntor e auditoria», do curso RAG, avaliação e fine-tuning.

| Arquivo | O que tem |
|---|---|
| `disjuntor.py` | O simulador da tarde do assistente e a investigação da auditoria. |
| `conversas-dia.csv` | As 37 conversas da tarde de 9 de dezembro, das 14h às 15h, com o que o modelo escreveria em cada rascunho. |
| `incidentes-dia.csv` | O que quebrou nessa tarde e quando. É o roteiro da simulação. |
| `auditoria-exercicio.csv` | A auditoria da manhã de 10 de dezembro, para o exercício. |
| `mudancas-exercicio.csv` | O que as equipes mudaram na manhã de 10 de dezembro. |
| `minha-investigacao.md` | O modelo para as suas respostas do exercício. |

As conversas, os rascunhos e os incidentes foram escritos para o curso. Nenhum modelo de linguagem roda aqui: o simulador lê o roteiro e decide o que cada chamada responde pela hora em que ela começa.

## Como rodar

Python 3.9 ou mais novo, só a biblioteca padrão. Rode de dentro dessa pasta:

```bash
python3 disjuntor.py comparar --conversas conversas-dia.csv --incidentes incidentes-dia.csv
python3 disjuntor.py simular --politica disjuntor --conversas conversas-dia.csv --incidentes incidentes-dia.csv
python3 disjuntor.py investigar --auditoria auditoria-disjuntor.csv
python3 disjuntor.py investigar --auditoria auditoria-disjuntor.csv --conversa D12
```

O `simular` grava a auditoria em `auditoria-<política>.csv` nessa pasta. Use `--auditoria outro-nome.csv` para escolher o nome. No `simular` e no `comparar`, `--abrir-apos` muda quantas falhas seguidas abrem o disjuntor (padrão 3) e `--aberto` muda quantos segundos ele fica aberto (padrão 300).

Se aparecer `erro:` e o programa sair com código 2, a mensagem diz o arquivo, a linha e o campo que não serviu. No Windows, troque `python3` por `py`.

## As colunas da auditoria

| Coluna | O que é |
|---|---|
| `hora` | quando a chamada começou |
| `conversa` | o id da conversa; `-` nas linhas do disjuntor |
| `assunto` | trocas, entregas, pagamentos, garantia ou outros |
| `parte` | busca, modelo, checagem ou conversa (a linha final, com a ação) |
| `tentativa` | na busca, 1, 2, 3; no modelo, rascunho.tentativa (`2.1` é a primeira chamada do segundo rascunho) |
| `resultado` | ok, erro, nada-que-vale, nao-chamada, passou, barrou, nao-achou, conflito, ou a ação final |
| `detalhe` | o motivo: timeout, o que a checagem barrou, os motivos da ação final |
| `duracao_s` | segundos da chamada; na linha da conversa, quanto o cliente esperou |

A auditoria não guarda a pergunta nem o texto do cliente.
