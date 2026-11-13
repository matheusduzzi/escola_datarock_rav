# 02. Chunking

Os arquivos da aula 02. Chunking. Rode os comandos de dentro dessa pasta.

| Arquivo | O que tem |
|---|---|
| `cortar.py` | Corta um documento por tamanho ou pela estrutura e conta o que aconteceu com cada pergunta. |
| `regulamento-clube.md` | O regulamento do Clube Exemplo, que a aula corta. |
| `perguntas-exemplo.json` | As seis perguntas da aula, com os textos do regulamento que cada resposta precisa. |
| `guia-entrega-agendada.md` | O guia da entrega agendada, do exercício. |
| `perguntas-exercicio.json` | As sete perguntas do exercício. |
| `plano-segmentacao.md` | O modelo do plano que você entrega. |

## Do que você precisa

Python 3.9 ou mais novo. O programa só usa a biblioteca padrão: não precisa instalar nada. No Windows, troque `python3` por `py`.

## Os três comandos

```bash
python3 cortar.py comparar regulamento-clube.md --perguntas perguntas-exemplo.json tamanho:500 estrutura:800
python3 cortar.py listar regulamento-clube.md estrutura:800
python3 cortar.py ver regulamento-clube.md tamanho:500 --perguntas perguntas-exemplo.json --pergunta C3
```

- `comparar` mostra, para cada jeito de cortar, quantos pedaços saíram, o tamanho deles, quanto texto foi indexado, quantos misturam seções, quantos começam no meio de uma frase e quantas respostas ficaram inteiras num pedaço.
- `listar` mostra o id, o tamanho e a seção de cada pedaço.
- `ver` mostra os pedaços onde está cada texto de uma pergunta. Com `--pedaco ID` no lugar de `--perguntas` e `--pergunta`, mostra um pedaço só.

## Os jeitos de cortar

| Jeito | O que faz |
|---|---|
| `tamanho:500` | corta o documento inteiro a cada 500 caracteres, sem partir palavra |
| `tamanho:500:100` | o mesmo, e cada pedaço começa repetindo uns 100 caracteres do anterior |
| `estrutura:800` | corta nos títulos `##` e `###`; se passar de 800 caracteres, corta por parágrafo, depois por linha da tabela ou item da lista, depois por frase; cada pedaço começa com os títulos e leva os campos da seção |

Os números são caracteres, não tokens. O modelo de embeddings conta em tokens: a aula 03 mede isso.

O programa também lê as políticas da loja, em que cada trecho é uma seção. O caminho `dados/...` é a pasta `dados/` da raiz do kit: o programa acha essa pasta de dentro de `02-chunking/`.

```bash
python3 cortar.py comparar dados/politicas/politicas.json tamanho:500 estrutura:800
```

## Quando dá erro

O programa sai com código 2 e uma linha `erro:` quando a entrada está errada: arquivo que não existe, jeito de cortar desconhecido, sobreposição maior ou igual ao tamanho, cabeçalho de campos faltando ou uma pergunta que pede um texto que não está no documento. Nesse caso ele não mostra resultado nenhum.

O programa não busca nada e não chama modelo. "Inteira" quer dizer que um pedaço tem todos os textos que a resposta precisa. Se a busca acha esse pedaço, só a aula 04 mostra.
