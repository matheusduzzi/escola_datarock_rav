# Kit do curso RAG, avaliação e fine-tuning

Os arquivos que você usa nas aulas: o diagnóstico e as políticas da Loja Exemplo.

## Como o kit está organizado

| Pasta | O que tem |
|---|---|
| `00-apresentacao/` | O [diagnóstico](00-apresentacao/diagnostico.md), o programa e o teste da tarefa 1 e a [folha de respostas](00-apresentacao/minhas-respostas.md). |
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
