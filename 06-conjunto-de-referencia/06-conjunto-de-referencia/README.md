# 06. Conjunto de referência

Os arquivos da aula. Rode os comandos de dentro dessa pasta. O programa lê as políticas em `dados/politicas/politicas.json`, na raiz do kit, e só usa a biblioteca padrão do Python 3.9 ou mais novo. No Windows, troque `python3` por `py`.

| Arquivo | O que é |
|---|---|
| `conjunto.py` | Checa cada linha do conjunto, separa em desenvolvimento e avaliação e trava a separação com sha256. |
| `conjunto-exemplo.csv` | As 26 perguntas da aula, já com grupo, tipo, trecho esperado e resposta esperada. |
| `conjunto-rascunho.csv` | O primeiro rascunho do desenvolvedor, com os erros que a aula mostra. |
| `perguntas-desenvolvedor-e-chat.csv` | As seis perguntas do desenvolvedor e as mesmas seis do jeito que o cliente escreveu, no formato do `lexical.py` da aula 04. |
| `meu-conjunto.csv` | O arquivo do exercício: as 26 perguntas da aula e as 12 da semana, com as colunas das 12 novas em branco. |
| `ficha-conjunto.md` | O modelo da ficha que você entrega no exercício. |

## As colunas do conjunto

| Coluna | O que vai nela | Exemplo |
|---|---|---|
| `id` | um código curto e único | `c01` |
| `grupo` | o nome da pergunta. A mesma pergunta escrita de outro jeito fica no mesmo grupo | `prazo-troca` |
| `pergunta` | o texto do jeito que o cliente escreveu | `Quantos dias eu tenho para trocar um produto?` |
| `perfil` | quem pergunta: `cliente`, `atendimento`, `supervisao` ou `financeiro` | `cliente` |
| `data` | o dia da pergunta, `AAAA-MM-DD`. Ele decide qual versão da política vale | `2026-11-10` |
| `tipo` | `termo exato`, `paráfrase`, `número`, `data`, `duas partes` ou `sem resposta` | `data` |
| `esperados` | o id do trecho que responde. Dois trechos vão separados por `\|` | `trocas@2#prazo` |
| `resposta` | a resposta curta, com os números escritos como no trecho | `20 dias da entrega` |
| `motivo` | só nas sem resposta: `fora das políticas` ou `outro perfil` | |

## Comandos

```bash
python3 conjunto.py checar conjunto-exemplo.csv
python3 conjunto.py checar conjunto-exemplo.csv --parecidas 0.4
python3 conjunto.py separar conjunto-exemplo.csv --pasta saida-exemplo
python3 conjunto.py trava saida-exemplo
```

| Comando | O que faz |
|---|---|
| `checar` | Mostra cada problema por linha e sai com código 2 se tiver algum. Sem problema, mostra quantas perguntas há de cada tipo. Também avisa quando duas perguntas de grupos diferentes são parecidas (a partir de 0,6 de palavras em comum; mude com `--parecidas`). O aviso não para o programa: você decide se é a mesma pergunta. |
| `separar` | Só roda se o `checar` não acha problema. Põe 40% dos grupos de cada tipo na avaliação (mude com `--avaliacao`), arredondado, com pelo menos um grupo de cada lado. Nas sem resposta, separa também pelo motivo. Quem escolhe os grupos é o sha256 do nome do grupo. Grava `dev.csv`, `avaliacao.csv` e `ficha.json` numa pasta nova e recusa uma pasta que já existe. |
| `trava` | Recalcula o sha256 da avaliação, do desenvolvimento e das políticas e compara com a `ficha.json`. Sai com código 2 se algum mudou. |

A busca da aula 04 roda nas perguntas do desenvolvedor e do chat. Esse comando roda da raiz do kit e precisa da pasta da aula 04:

```bash
python3 04-busca-hibrida-e-reranking/lexical.py --perguntas 06-conjunto-de-referencia/perguntas-desenvolvedor-e-chat.csv
```

## Quando o programa para

O programa para com `erro:` e código 2 quando falta o arquivo, quando falta uma coluna, quando o CSV não tem pergunta, quando o conjunto tem problema e você pede `separar`, quando a pasta da separação já existe, quando um tipo fica só de um lado, quando `--avaliacao` não fica entre 0 e 1 e quando a `trava` acha arquivo mudado. Leia a mensagem, corrija e rode de novo. Para mudar uma separação já feita, faça outra numa pasta nova.

## Se precisar de ajuda

Deixe um comentário na aula. Conte o objetivo, o comando que você rodou, a saída que apareceu e o que já tentou, sem dados pessoais.
