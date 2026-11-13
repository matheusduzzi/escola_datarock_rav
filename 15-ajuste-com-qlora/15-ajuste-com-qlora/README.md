# 15. Ajuste com QLoRA

Os arquivos da aula «Ajuste com QLoRA»: as respostas boas do atendimento da Loja Exemplo, o programa que separa treino, validação e avaliação, o ajuste pronto do TI e os scripts de treino para quem tem placa de vídeo.

## O que tem aqui

| Arquivo ou pasta | O que é |
|---|---|
| `exemplos.jsonl` | 70 perguntas de clientes com a resposta boa do atendimento, de fevereiro a novembro, e os trechos das políticas que valiam no dia |
| `exemplos-dezembro.jsonl` | o lote de dezembro, para o exercício |
| `ajuste.py` | separa os exemplos, lê o registro do treino e compara respostas. Só usa a biblioteca padrão |
| `prompts/` | o prompt curto e o prompt com três exemplos do tom da loja |
| `respostas/` | as respostas de cada variante nas perguntas da avaliação: o modelo sem ajuste com os dois prompts e o ajuste do TI em dois checkpoints |
| `ajuste-ti/` | a configuração e o registro do treino do TI, e o teste que deu "10 de 10" |
| `ajuste-2/` | o segundo ajuste do TI, para o exercício |
| `treinar_qlora.py`, `responder.py`, `requisitos-treino.txt` | o caminho com placa de vídeo: treinar o seu adaptador e gerar as respostas dele |
| `relatorio.md` | o modelo do relatório que você entrega |

O `ajuste.py` lê as políticas em `../dados/politicas/politicas.json`. Rode tudo de dentro dessa pasta. No Windows, troque `python3` por `py`.

O registro e as respostas das pastas `ajuste-ti/`, `ajuste-2/` e `respostas/` foram escritos para o curso. Quem tem placa troca essas respostas pelas do próprio modelo.

## Os comandos da aula

```bash
python3 ajuste.py separar --exemplos exemplos.jsonl --saida separado
python3 ajuste.py comparar --avaliacao separado/avaliacao.jsonl --treino separado/treino.jsonl --respostas ajuste-ti/teste-do-ti.jsonl
python3 ajuste.py registro --registro ajuste-ti/registro-treino.csv
python3 ajuste.py comparar --avaliacao separado/avaliacao.jsonl --treino separado/treino.jsonl --respostas respostas/base.jsonl --respostas respostas/base-3-exemplos.jsonl --respostas respostas/qlora-passo-24.jsonl --respostas respostas/qlora-passo-60.jsonl
```

O segundo comando termina com `erro:` de propósito: o teste do TI usa perguntas do treino.

Quando um arquivo tem problema, o `ajuste.py` para com uma linha `erro:` e não grava nada. Por exemplo, um id repetido, um trecho que não existe ou um arquivo de respostas que pulou uma pergunta da avaliação.

## Se você tem placa de vídeo

O treino pede Python 3.11 ou mais novo, placa NVIDIA com CUDA e as bibliotecas de `requisitos-treino.txt`. Instale primeiro o torch com CUDA, pelo comando que a página pytorch.org mostra para a sua placa. Depois:

```bash
pip install -r requisitos-treino.txt
python3 treinar_qlora.py --checar --treino separado/treino.jsonl --validacao separado/validacao.jsonl
python3 treinar_qlora.py --treino separado/treino.jsonl --validacao separado/validacao.jsonl --saida meu-ajuste
python3 ajuste.py registro --registro meu-ajuste/registro-treino.csv
python3 responder.py --avaliacao separado/avaliacao.jsonl --variante meu-passo-24 --adaptador meu-ajuste/checkpoint-24 --saida minhas/meu-passo-24.jsonl
```

O `--checar` roda em qualquer computador e não instala nada: ele lê os arquivos e mostra a configuração. O treino baixa o modelo Qwen2.5-1.5B-Instruct, de licença Apache 2.0. Ele salva um checkpoint por época em `meu-ajuste/` e anota o pico de memória da placa em `meu-ajuste/config.json`. Troque o 24 pelo passo que o seu registro apontar. Gere também as respostas do modelo sem ajuste, sem o `--adaptador`, com os dois prompts.

Os scripts de treino seguem a documentação das versões de `requisitos-treino.txt`. Eles não rodaram no computador em que a aula foi escrita, que não tem placa NVIDIA. Se der erro, deixe um comentário na aula.

## Se precisar de ajuda

Deixe um comentário na aula. Conte o objetivo, o comando que você rodou, a saída que apareceu e o que já tentou, sem dados pessoais. Para o treino, conte também a placa e a versão das bibliotecas (`pip show transformers peft trl bitsandbytes`).
