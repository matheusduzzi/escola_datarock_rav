# 08. LLM como juiz

Os arquivos da aula. Rode os comandos de dentro dessa pasta. Os dois programas só usam a biblioteca padrão do Python 3.9 ou mais novo. No Windows, troque `python3` por `py`.

| Arquivo | O que é |
|---|---|
| `regras-atendimento.md` | As três regras de como o assistente atende: `identificacao`, `saude` e `acolhimento`. |
| `conversas.csv` | 12 conversas do atendimento: a mensagem do cliente e a resposta do assistente. |
| `pessoas.csv` | A marca de duas pessoas para cada conversa e cada regra, e o final que elas decidiram juntas. |
| `juiz-mesma.csv` | Os vereditos de um juiz da mesma família do modelo do assistente, em 5 rodadas. |
| `juiz-outra.csv` | Os vereditos de um juiz de outra família, nas mesmas 5 rodadas. |
| `pares.csv` | 6 mensagens com duas respostas: a do prompt atual e a do prompt novo, e a escolha das pessoas. |
| `pares-juiz-mesma.csv`, `pares-juiz-outra.csv` | A escolha de cada juiz nos 6 pares, nas duas ordens. |
| `leva2-*.csv` | O exercício: 6 conversas novas, a marca da primeira pessoa e os vereditos dos dois juízes. |
| `calibrar.py` | Compara cada juiz com as pessoas e lista as divergências. |
| `juiz.py` | Roda um juiz de verdade e grava os vereditos no mesmo formato. |
| `prompt-notas.md`, `prompt-pares.md` | O que o `juiz.py` manda para o modelo. |
| `protocolo.md` | O modelo do protocolo que você entrega. |

As conversas, as marcas das pessoas e os vereditos dos dois juízes foram escritos para o curso: nenhum modelo de linguagem rodou para gerar esses arquivos. Eles repetem os tipos de erro que os artigos da aula descrevem. Com o `juiz.py` e uma conta num provedor, você gera os seus vereditos e roda o mesmo `calibrar.py`.

## As colunas

| Arquivo | Coluna | O que vai nela |
|---|---|---|
| `pessoas.csv` | `id`, `regra` | a conversa e a regra. Uma linha para cada par conversa e regra |
| `pessoas.csv` | `pessoa_1`, `pessoa_2` | a marca de cada pessoa: `cumpre`, `quebra` ou `nao-se-aplica` |
| `pessoas.csv` | `final` | a marca que vale, decidida pelas duas depois de conversar |
| juiz | `rodada` | 1, 2, 3... O mesmo conjunto, rodado de novo |
| juiz | `veredito` | `cumpre`, `quebra` ou `nao-se-aplica` |
| `pares.csv` | `atual`, `novo` | as duas respostas para a mesma mensagem |
| `pares.csv` | `pessoas` | `atual`, `novo` ou `empate` |
| pares do juiz | `ordem` | `atual-novo` (a resposta atual veio em 1º) ou `novo-atual` |
| pares do juiz | `escolha` | `1` (a primeira), `2` (a segunda) ou `empate` |

## Comandos

```bash
python3 calibrar.py notas conversas.csv pessoas.csv juiz-mesma.csv juiz-outra.csv
python3 calibrar.py notas conversas.csv pessoas.csv juiz-mesma.csv juiz-outra.csv --detalhe s04
python3 calibrar.py pares pares.csv pares-juiz-mesma.csv pares-juiz-outra.csv
python3 calibrar.py notas leva2-conversas.csv leva2-pessoas.csv leva2-juiz-mesma.csv leva2-juiz-outra.csv
```

O veredito de cada juiz é a maioria das rodadas. Empate entre as rodadas sai como `sem maioria` e conta como divergência. Nos pares, quando a escolha muda com a ordem, o par conta como empate.

Com arquivo errado, o `calibrar.py` lista os problemas e sai com código 2, sem mostrar números: coluna faltando, arquivo vazio, marca vazia ou fora das três, regra que não existe, conversa sem as três regras, item repetido, rodada sem todos os itens, par sem as duas ordens.

## Rodar um juiz de verdade

O `juiz.py` fala com qualquer serviço compatível com a API de chat da OpenAI. Um exemplo é a OpenRouter, que dá acesso a modelos de várias empresas com uma conta só. Ela pede conta e crédito, e o nome de cada modelo começa pela empresa que o fez: é por ali que você vê a família.

Antes de gastar, veja quantas chamadas e tokens a rodada pede e o prompt de uma conversa:

```bash
python3 juiz.py notas conversas.csv --estimar --rodadas 5
python3 juiz.py notas conversas.csv --mostrar s04
```

Depois defina o endereço e a chave no terminal. A chave fica só na variável, fora dos arquivos:

```bash
export JUIZ_BASE_URL=https://openrouter.ai/api/v1
export JUIZ_CHAVE=sua-chave
python3 juiz.py notas conversas.csv --modelo NOME-DO-MODELO --rodadas 5 --saida meu-juiz.csv
python3 calibrar.py notas conversas.csv pessoas.csv meu-juiz.csv juiz-outra.csv
```

No PowerShell do Windows, use `$env:JUIZ_BASE_URL="https://openrouter.ai/api/v1"` e `$env:JUIZ_CHAVE="sua-chave"`.

Para os pares: `python3 juiz.py pares pares.csv --modelo NOME-DO-MODELO --saida pares-meu-juiz.csv`. Ele roda cada par nas duas ordens.

O `juiz.py` só grava o arquivo no fim. Sem as variáveis, ou com uma resposta fora do formato duas vezes seguidas, ele sai com código 2 e não grava nada. Se o serviço recusar a chamada, ele sai com código 1 e mostra o código que o serviço deu.

## Se precisar de ajuda

Deixe um comentário na aula. Conte o objetivo, o comando que você rodou, a saída que apareceu e o que já tentou, sem dados pessoais e sem a sua chave.
