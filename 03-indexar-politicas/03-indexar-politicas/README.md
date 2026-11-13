# 03. Indexar políticas

Os arquivos da aula 03. Indexar políticas. Rode os comandos de dentro dessa pasta. O caminho `dados/...` é a pasta `dados/` da raiz do kit: o programa acha essa pasta de dentro de `03-indexar-politicas/`.

| Arquivo | O que tem |
|---|---|
| `indexar.py` | Constrói o índice das políticas, consulta, mostra os vizinhos de um pedaço, roda as consultas de teste e refaz o índice para ver se ele bate com as políticas. |
| `consultas-teste.json` | As três consultas de teste da aula. |
| `indice-colega.jsonl` e `indice-colega.manifesto.json` | O índice que o colega mandou, da prática guiada. |
| `lote-janeiro.json` | As mudanças de janeiro, do exercício. |
| `ficha-indice.md` | O modelo da ficha que você entrega no exercício. |
| `contar_tokens.py` | Conta os tokens de cada pedaço com o vocabulário do modelo `all-MiniLM-L6-v2`. |
| `pedaco-maior-clube.txt` | O maior pedaço do regulamento do Clube na aula 02, com 639 caracteres. |

## Do que você precisa

Python 3.9 ou mais novo. Os dois programas só usam a biblioteca padrão: não precisa instalar nada. No Windows, troque `python3` por `py`.

## Os comandos da aula

```bash
python3 indexar.py construir
python3 indexar.py consultar "Quantos dias eu tenho para trocar?" --perfil cliente --data 2026-11-13
python3 indexar.py vizinhos "trocas@2#prazo/1"
python3 indexar.py testar consultas-teste.json
python3 indexar.py verificar
```

| Comando | O que faz |
|---|---|
| `construir` | Lê as políticas e grava `indice.jsonl`, um registro por pedaço, e `indice.manifesto.json`. Com `--lote arquivo.json`, um trecho do lote com o mesmo id de um trecho que já existe toma o lugar dele. Com `--anterior indice.jsonl`, o vetor de um pedaço cujo texto não mudou vem do índice anterior. Com `--saida outro.jsonl`, grava com outro nome. |
| `consultar "pergunta" --perfil P --data AAAA-MM-DD` | Os 3 pedaços mais parecidos com a pergunta entre os que o perfil lê nesse dia. `--k 5` muda a quantidade. `--filtro depois` ordena todos e filtra só os primeiros. `--filtro nenhum` não filtra. |
| `vizinhos "pedaço"` | Os pedaços com o vetor mais parecido com o de um pedaço. |
| `testar arquivo.json` | Roda cada consulta de teste e diz se o pedaço certo veio em 1º e se algum que não podia vir apareceu. |
| `verificar` | Refaz o índice a partir das políticas e do manifesto e diz o que não bate. |

`consultar`, `vizinhos`, `testar` e `verificar` leem `indice.jsonl` se você não disser outro com `--indice`. Os perfis são `cliente`, `atendimento`, `supervisao` e `financeiro`.

## O embedding desse programa

O `indexar.py` faz o vetor com pedaços de 3 a 5 letras do texto, espalhados por um hash em 512 posições. Ele compara letras, não sentido. Por isso o resultado sai igual em qualquer máquina e nada precisa ser instalado. A aula 09 troca esse embedding pelo de um modelo de verdade. O registro e o manifesto continuam com os mesmos campos.

## As consultas de teste

Cada consulta tem `id`, `pergunta`, `perfil`, `data` e `k` (3 se faltar). Ela diz o trecho que precisa vir em 1º (`primeiro`), os trechos que não podem aparecer entre os k primeiros (`nao_pode`) ou os dois. Os ids são de trecho, sem o `/1`: `trocas@2#prazo`.

## Contar tokens

O `contar_tokens.py` precisa do vocabulário do modelo, um arquivo de texto de 231.508 bytes. Baixe com:

```bash
curl -L -o vocab.txt https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/vocab.txt
python3 contar_tokens.py --vocab vocab.txt indice.jsonl pedaco-maior-clube.txt
```

O sha256 do arquivo é `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3`. No macOS e no Linux, `shasum -a 256 vocab.txt` mostra o seu. No Windows, `certutil -hashfile vocab.txt SHA256`. O modelo tem licença Apache 2.0.

O programa refaz os passos do tokenizador desse modelo com o vocabulário dele: minúsculas, sem acento, pontuação à parte e cada palavra quebrada nos maiores pedaços que existem no vocabulário. A biblioteca do modelo não é usada.

## Quando dá erro

- **Código 1**: o resultado não serve. No `testar`, alguma consulta falhou. No `verificar`, o índice não bate com as políticas ou com o manifesto. No `consultar`, duas versões aprovadas da mesma seção valem no mesmo dia. No `contar_tokens.py`, algum pedaço passou do limite.
- **Código 2**, com uma linha `erro:`: falta algo ou algo está no formato errado. Por exemplo: arquivo que não existe, JSON quebrado, trecho sem algum dos dez campos, id que não é `documento@versao#secao`, `fim` igual ou antes do `inicio`, perfil ou status que não existe, data fora do formato, pedaço com mais de 800 caracteres ou índice sem o manifesto ao lado. Nesse caso o `construir` não grava nada.

O `construir` não muda o arquivo das políticas nem o lote. Ele só grava o índice e o manifesto com o nome de `--saida`.
