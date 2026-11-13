# Diagnóstico: por onde começar em RAG, avaliação e fine-tuning

A coordenadora do atendimento da Loja Exemplo quer um assistente que responda os clientes pelas políticas da loja. Ela tem um medo: o assistente citar a política certa com o prazo errado. Antes de montar a primeira busca, eu refiz seis contas que o curso usa desde a aula 01. As tarefas abaixo são essas contas.

As cinco primeiras vêm dos cursos anteriores. São Python com teste, cosseno entre vetores, acerto da busca, fidelidade ao trecho e a troca entre qualidade, tempo e custo. A sexta é sobre memória para ajustar um modelo. Se ela travar, tudo bem: a aula 14 ensina essa parte.

O diagnóstico não é prova e não tem nota. Ele mostra por onde você começa. Anote na [folha de respostas](minhas-respostas.md) a conta que fez, o comando que rodou e a saída que apareceu. Só depois compare com as respostas.

A tarefa 1 roda no terminal, de dentro da pasta `00-apresentacao/`. As outras são de lápis e papel ou calculadora. No Windows, troque `python3` por `py`.

## Tarefa 1. Que trechos o assistente pode usar hoje

O arquivo `../dados/politicas/politicas.json` tem 16 trechos das políticas da loja. O [LEIA-ME](../dados/politicas/LEIA-ME.md) explica cada campo. Em `tarefa1.py`, escreva a função `vigentes(trechos, perfil, dia)`. Ela retorna a lista dos `id` que aquele perfil pode ler naquele dia, em ordem alfabética. Um trecho entra quando:

| Regra | Campo |
|---|---|
| está aprovado | `status` igual a `aprovado` |
| o perfil pode ler | `perfil` está em `perfis` |
| já começou | `inicio` menor ou igual ao dia |
| ainda não acabou | `fim` é `null`, ou o dia é menor que `fim` |

Se duas versões da mesma seção do mesmo documento entram no mesmo dia, a função para com `ValueError`. Ela também não pode alterar a lista que recebeu.

Rode:

```bash
python3 tarefa1.py
python3 testar_tarefa1.py
```

Enquanto a função não existe, os dois comandos param com `NotImplementedError`. Quando os seis testes passarem, anote:

1. As três linhas que `tarefa1.py` mostrou.
2. Por que o dia em `fim` fica de fora? O que aconteceria em 1º de outubro se ele entrasse?
3. Por que parar com erro quando duas versões valem no mesmo dia, em vez de pegar a mais nova?

## Tarefa 2. O vetor mais parecido é o certo?

A pergunta "quantos dias eu tenho para trocar?" virou o vetor q = (1, 2, 2). Três trechos viraram estes vetores:

| Trecho | Vetor |
|---|---|
| `trocas@1#prazo` | (2, 4, 4) |
| `trocas@2#prazo` | (1, 2, 1) |
| `pagamentos@1#parcelamento` | (2, 0, 1) |

1. Calcule o cosseno de q com cada um, com três casas. Coloque em ordem do maior para o menor.
2. O vetor de `trocas@1#prazo` tem o dobro do tamanho de q. Por que o cosseno dá o valor máximo mesmo assim?
3. Se a busca manda só o primeiro trecho para o modelo, o que o cliente lê em 5 de novembro de 2026? Use o resultado da tarefa 1.
4. Um cosseno de 0,95 quer dizer 95% de chance de o trecho responder a pergunta?

## Tarefa 3. Quantas vezes a busca achou o trecho certo

Imagine uma busca que recebeu cinco perguntas. A tabela mostra os três primeiros trechos que ela retornou para cada uma. A coluna "trecho certo" diz qual trecho responde a pergunta em 5 de novembro de 2026.

| Pergunta | Trecho certo | 1º | 2º | 3º |
|---|---|---|---|---|
| p1. Quantos dias eu tenho para trocar? | `trocas@2#prazo` | `trocas@1#prazo` | `trocas@2#prazo` | `trocas@1#tamanho` |
| p2. Acima de qual valor o frete é grátis? | `entregas@1#frete` | `entregas@1#frete` | `entregas@1#prazo` | `pagamentos@1#boleto-pix` |
| p3. Em quantas vezes sem juros posso parcelar? | `pagamentos@1#parcelamento` | `pagamentos@1#duplicidade` | `pagamentos@1#boleto-pix` | `garantia@1#estendida` |
| p4. Meu produto chegou quebrado, o que eu faço? | `trocas@1#defeito` | `garantia@1#eletrodomesticos` | `trocas@1#defeito` | `entregas@1#extravio` |
| p5. Vocês aceitam criptomoeda? | nenhum | `pagamentos@1#boleto-pix` | `pagamentos@1#parcelamento` | `pagamentos@1#duplicidade` |

1. Em quantas perguntas o trecho certo veio em 1º? E entre os três primeiros? Diga a conta e a fração.
2. A p5 entra nessa conta? Se não entra, como você mede o que a busca fez com ela?
3. Na p1, o trecho certo apareceu, mas em 2º. O problema está na ordem ou em outra coisa?

## Tarefa 4. A resposta diz o que o trecho diz?

Três respostas do assistente em 5 de novembro de 2026, cada uma com o trecho que ela cita:

| Pergunta | Resposta do assistente | Trecho citado |
|---|---|---|
| p1 | "Você tem 30 dias corridos para pedir a troca." | `trocas@2#prazo` |
| p4 | "Envie uma foto pelo atendimento em até 7 dias da entrega." | `trocas@1#defeito` |
| p5 | "Aceitamos pix e boleto." | `pagamentos@1#boleto-pix` |

Leia o texto dos três trechos em `politicas.json`. Para cada resposta, diga se ela é fiel ao trecho, se contradiz o trecho ou se não responde a pergunta. Depois escreva o que o assistente deveria ter respondido na p5.

## Tarefa 5. Melhor, mais lenta e mais cara

Imagine duas buscas testadas nas mesmas 40 perguntas: 30 têm resposta nas políticas e 10 não têm. A busca A procura por palavras. A busca B procura por palavras e depois reordena os trechos com outro modelo.

| | Busca A | Busca B |
|---|---|---|
| Trecho certo entre os três primeiros, nas 30 com resposta | 22 | 26 |
| Perguntas sem resposta em que o assistente disse que não sabia | 6 de 10 | 6 de 10 |
| Tempo mediano por pergunta | 0,4 s | 1,6 s |
| Custo por 1.000 perguntas | R$ 0,50 | R$ 3,20 |

Os preços são inventados para a conta.

1. Qual a taxa de acerto de cada uma, em porcentagem? Quantas perguntas a B acertou a mais?
2. O atendimento recebe 50 mil perguntas por mês. Quanto cada busca custa no mês?
3. O atendimento pede resposta em até 1 segundo, na mediana. Qual delas serve?
4. O que falta na tabela para dizer que a B é melhor de verdade?

## Tarefa 6. Cabe na sua máquina?

Um parâmetro de um modelo ocupa 2 bytes guardado em 16 bits e meio byte em 4 bits. Conte 1 GB como 1 bilhão de bytes.

1. Quanto ocupam só os pesos de um modelo de 1 bilhão de parâmetros em 16 bits? E em 4 bits?
2. Faça a mesma conta para um modelo de 7 bilhões de parâmetros.
3. No treino, o que mais ocupa memória além dos pesos?
4. Anote a memória da sua placa de vídeo, ou anote que você não tem uma. Com isso, você treina na aula 15 ou analisa um ajuste pronto?

## Depois das tarefas

Compare as suas anotações com as respostas da aula 00. Para cada tarefa, marque: "fiz sozinho", "fiz com consulta" ou "não consegui". A aula 00 também diz qual aula fazer antes quando uma tarefa travar.
