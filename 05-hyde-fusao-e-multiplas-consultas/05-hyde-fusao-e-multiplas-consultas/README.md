# 05. HyDE, fusão e múltiplas consultas

Os arquivos da aula. Rode os comandos de dentro dessa pasta. O programa lê as políticas em `dados/politicas/politicas.json`, na raiz do kit, e só usa a biblioteca padrão do Python 3.9 ou mais novo. No Windows, troque `python3` por `py`.

| Arquivo | O que é |
|---|---|
| `expandir.py` | Busca a mesma pergunta de quatro jeitos: a pergunta original, múltiplas consultas com fusão pela posição, o texto inventado (a ideia do HyDE) e o Query2doc. A busca é o BM25 da aula 04, com o mesmo filtro de perfil, data e status em cada busca. |
| `expansoes-exemplo.json` | As reescritas e os textos inventados das seis perguntas da aula. |
| `perguntas-exemplo.csv` | As seis perguntas da aula, com tipo e trecho esperado. |
| `expansoes-exercicio.json` | As reescritas e os textos inventados das oito perguntas do exercício. |
| `perguntas-exercicio.csv` | As oito perguntas do exercício, com tipo e trecho esperado. |
| `criterio-adocao.md` | O modelo do critério que você entrega no exercício. |

Os dois arquivos de expansões foram escritos à mão, do jeito que um modelo costuma responder aos pedidos que estão dentro deles. Nenhum modelo rodou para gerar esses textos. Os textos inventados têm números e regras que a loja não tem, de propósito: é isso que o modelo faz quando escreve sem ler as políticas.

## As quatro estratégias

| Nome no programa | O que vai para a busca | Chamadas ao modelo | Buscas |
|---|---|---|---|
| `original` | a pergunta do cliente | 0 | 1 |
| `multiplas` | a pergunta e cada reescrita, uma busca por texto; os 5 primeiros de cada busca se juntam pela posição (constante 60) | 1 | 4 |
| `hipotetico` | só o texto inventado | 1 | 1 |
| `q2d` | a pergunta repetida 5 vezes mais o texto inventado | 1 | 1 |

## Comandos da aula

```bash
python3 expandir.py --perguntas perguntas-exemplo.csv --expansoes expansoes-exemplo.json
python3 expandir.py "Quantos dias eu tenho para trocar?" --expansoes expansoes-exemplo.json --detalhe
python3 expandir.py --perguntas perguntas-exemplo.csv --expansoes expansoes-exemplo.json --estrategias multiplas --sem-original
```

Opções:

| Opção | Padrão | O que faz |
|---|---|---|
| `--estrategias` | as quatro | lista separada por vírgula, por exemplo `original,q2d` |
| `--detalhe` | desligado | em `multiplas`, mostra as reescritas e a posição do trecho em cada busca; em `hipotetico` e `q2d`, as palavras que mais deram pontos ao 1º colocado |
| `--sem-original` | desligado | em `multiplas`, busca só com as reescritas |
| `--por-consulta` | 5 | em `multiplas`, quantos trechos de cada busca entram na fusão; `0` leva todos |
| `--k` | 3 | quantos resultados mostrar ou contar |
| `--data AAAA-MM-DD` | `2026-11-10` | o dia da pergunta; decide qual versão vale |
| `--perfil` | `cliente` | quem pergunta: `cliente`, `atendimento`, `supervisao` ou `financeiro` |

Uma pergunta sozinha só roda se estiver escrita igual no arquivo de expansões, com a mesma pontuação. No CSV, as colunas são `id`, `tipo`, `pergunta` e `esperado`; pergunta sem resposta fica com `esperado` vazio.

## Quando o programa para

O programa para com `erro:` e código 2 quando falta algo: pergunta vazia, pergunta que não está no arquivo de expansões, estratégia com nome errado, reescrita vazia, texto inventado vazio, JSON quebrado, data fora do formato, perfil que não existe, `--k` menor que 1 ou um trecho esperado que o perfil não pode ler naquela data. Leia a mensagem, corrija a entrada e rode de novo.

## Se precisar de ajuda

Deixe um comentário na aula. Conte o objetivo, o comando que você rodou, a saída que apareceu e o que já tentou, sem dados pessoais.
