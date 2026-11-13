# Kit do curso RAG, avaliação e fine-tuning

Os arquivos que você usa nas aulas: o diagnóstico e as políticas da Loja Exemplo.

## Como o kit está organizado

| Pasta | O que tem |
|---|---|
| `00-apresentacao/` | O [diagnóstico](00-apresentacao/diagnostico.md), o programa e o teste da tarefa 1, a [folha de respostas](00-apresentacao/minhas-respostas.md) e a [folha da sua ordem de estudo](00-apresentacao/minha-ordem.md). |
| `dados/politicas/` | 16 trechos das políticas da loja, com versão, datas e quem pode ler cada um. Ver [dados/politicas/LEIA-ME.md](dados/politicas/LEIA-ME.md). |
| `NN-titulo/` | Uma pasta por aula, com o número e o título da aula. Elas entram no kit junto com as aulas. |

Os comandos das aulas rodam de dentro da pasta da aula. Quando uma aula usa as políticas, ela diz o caminho, por exemplo `../dados/politicas/politicas.json`.

## Do que você precisa

- Python 3.9 ou mais novo. O diagnóstico só usa a biblioteca padrão: não precisa instalar nada.
- Um editor de código e um terminal.

As bibliotecas de embeddings, de busca, de avaliação e de treino entram na primeira aula que usa cada uma. Essa aula traz a versão, o Python mínimo e o comando de instalação. O treino da aula 15 pede placa de vídeo; quem não tem faz a aula pelo ajuste pronto.

Veja se o seu Python roda o kit:

```bash
cd 00-apresentacao
python3 testar_tarefa1.py
```

Antes de você escrever a função da tarefa 1, a saída termina com `0 de 6 testes passaram` e cada teste mostra `NotImplementedError`. Isso quer dizer que o Python achou os arquivos. Se aparecer `No such file or directory`, você não está dentro de `00-apresentacao/`. No Windows, troque `python3` por `py`.

## Se precisar de ajuda

Deixe um comentário na aula. Conte o objetivo, o comando que você rodou, a saída que apareceu e o que já tentou, sem dados pessoais.

## Licença

A licença de uso e redistribuição do kit ainda vai ser definida pela Escola Datarock. Até lá, use os arquivos para estudar o curso. A Loja Exemplo é inventada, e as políticas foram escritas para o curso.

## Aulas com arquivos neste kit

| Pasta | Aula |
|---|---|
| [00-apresentacao/](00-apresentacao/) | Apresentação |
| [01-corpus-versao-e-permissao/](01-corpus-versao-e-permissao/) | Corpus, versão e permissão |
| [02-chunking/](02-chunking/) | Chunking |
| [03-indexar-politicas/](03-indexar-politicas/) | Indexar políticas |
| [05-hyde-fusao-e-multiplas-consultas/](05-hyde-fusao-e-multiplas-consultas/) | HyDE, fusão e múltiplas consultas |
| [06-conjunto-de-referencia/](06-conjunto-de-referencia/) | Conjunto de referência |
| [07-avaliar-recuperacao-e-resposta/](07-avaliar-recuperacao-e-resposta/) | Avaliar recuperação e resposta |
| [08-llm-como-juiz/](08-llm-como-juiz/) | LLM como juiz |
| [09-benchmark-de-estrategias/](09-benchmark-de-estrategias/) | Benchmark de estratégias |
| [10-alucinacao-e-incerteza/](10-alucinacao-e-incerteza/) | Alucinação e incerteza |
| [11-plano-b-e-escalonamento/](11-plano-b-e-escalonamento/) | Plano B e escalonamento |
| [12-disjuntor-e-auditoria/](12-disjuntor-e-auditoria/) | Disjuntor e auditoria |
| [13-prompt-rag-ou-fine-tuning/](13-prompt-rag-ou-fine-tuning/) | Prompt, RAG ou fine-tuning |
| [14-lora-qlora-e-peft/](14-lora-qlora-e-peft/) | LoRA, QLoRA e PEFT |
| [15-ajuste-com-qlora/](15-ajuste-com-qlora/) | Ajuste com QLoRA |
| [16-reviews-da-loja-exemplo/](16-reviews-da-loja-exemplo/) | Reviews da Loja Exemplo |
