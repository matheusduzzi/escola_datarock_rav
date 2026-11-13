# Os oito casos da quinzena

A coordenadora juntou o que o atendimento e a equipe do assistente anotaram nas duas semanas depois da matriz. Cada caso já vem com o diagnóstico: o que a busca trouxe, o que a resposta fez e o que já foi tentado. Os casos foram escritos para o curso. Os trechos e os prazos são os de `dados/politicas/politicas.json`.

## E01. A parcela de R$ 25

- **Pergunta:** "Dá para fazer em 6 vezes numa compra de R$ 150?"
- **Trechos que o assistente leu:** `pagamentos@1#parcelamento` em 1º, `pagamentos@1#boleto-pix` em 2º.
- **Rascunho da resposta:** "Sim, você pode parcelar em 6 vezes de R$ 25,00 sem juros."
- **Diagnóstico:** os trechos bastam; o rascunho contradiz o trecho, que pede parcela mínima de R$ 30,00. Resposta sem suporte.
- **Quantas vezes:** 4 vezes na quinzena, sempre com parcela abaixo de R$ 30,00. Nas 4, o plano B da aula 11 barrou o rascunho, porque R$ 25,00 não está no trecho, e o cliente recebeu "não sei".
- **Já tentado:** nada. O prompt de hoje não fala da parcela mínima nem de conta com o trecho.

## E02. Os 40 dias

- **Pergunta:** "Quanto tempo eu tenho para trocar um tênis que não usei?"
- **Trechos que o assistente leu:** `trocas@3#prazo` em 1º, `trocas@2#prazo` em 2º.
- **Resposta:** "Você tem 40 dias corridos, contados da entrega, para pedir a troca."
- **Diagnóstico:** trecho que não vale. A versão 3 do prazo ainda é rascunho. Fonte em conflito.
- **Desde quando:** desde a quinta-feira em que a equipe refez o índice das políticas. No índice novo, os trechos estão sem o campo `status`. O filtro do plano B tira o rascunho pelo `status`, e ele chegou vazio.
- **Quantas vezes:** 11 perguntas de prazo de troca desde a quinta-feira, todas com o rascunho em 1º.
- **Já tentado:** nada.

## E03. O presente sem nota

- **Pergunta:** "Ganhei uma blusa de presente, sem a nota. Dá para trocar o tamanho?"
- **Trechos que o assistente leu:** `trocas@1#tamanho` em 1º, `trocas@2#prazo` em 2º, `trocas@1#defeito` em 3º.
- **Resposta:** "Sim. É só apresentar a nota fiscal ou o número do pedido em nome de quem comprou."
- **Diagnóstico:** nenhum trecho fala de presente, de nota fiscal ou de quem comprou. O conjunto de referência marca essa pergunta como sem resposta. Resposta sem suporte, numa pergunta em que a loja não tem regra.
- **Quantas vezes:** 6 vezes na quinzena. O atendimento conta que esse pedido sobe muito em janeiro.
- **Já tentado:** nada.

## E04. A garantia estendida

- **Pergunta:** "A garantia estendida soma quanto tempo?"
- **Trechos que o assistente leu:** `garantia@1#eletrodomesticos` em 1º, `trocas@1#defeito` em 2º, `entregas@1#prazo` em 3º. O trecho `garantia@1#estendida` veio em 5º e ficou de fora, porque o assistente lê só os 3 primeiros.
- **Resposta:** "Nos trechos que eu tenho, não achei quanto tempo a garantia estendida soma. Vou passar para o atendimento confirmar."
- **Diagnóstico:** faltou trecho; a resposta disse o que faltou. Fonte insuficiente.
- **Quantas vezes:** 3 vezes na quinzena.
- **Já tentado:** nada.

## E05. O resumo da passagem para uma pessoa

- **O que acontece:** quando o assistente passa a conversa para uma pessoa, ele escreve um resumo para o painel do atendimento, com três campos: `motivo`, `pedido` e `resumo`. O painel lê o campo `pedido` para abrir o pedido do cliente.
- **Diagnóstico:** em 7 das 40 passagens da quinzena, o resumo veio sem o campo `pedido`, com o número do pedido escrito dentro do `resumo`. Nas 7, o cliente tinha dado o número na conversa. A busca não participa desse passo.
- **Já tentado:** o prompt de hoje lista os três campos numa frase. Não tem exemplo e o assistente não valida o formato antes de mandar ao painel.

## E06. O tom e a conta

- **O que aconteceu:** depois da matriz, o prompt ganhou 14 respostas do atendimento como exemplo de tom. O pedido fixo passou de 600 para 2.600 palavras, e 2.000 delas são os exemplos.
- **O que foi medido:** uma pessoa da equipe leu 50 respostas com a rubrica de tom antes e depois. O tom passou em 12 de 50 antes e em 46 de 50 depois. A fidelidade no conjunto de referência não caiu.
- **O problema:** a conta mensal do modelo dobrou desde que os exemplos entraram. A equipe quer manter o tom e voltar ao custo de antes.
- **Já tentado:** nada para o custo. Os 14 exemplos são os únicos escritos até agora, todos sem dados de cliente.

## E07. A queda das 16h

- **O que aconteceu:** na terça, das 16:02 às 16:15, o provedor do modelo respondeu erro em todas as chamadas. A auditoria anota a parte `modelo` e o resultado `erro`. O disjuntor abriu às 16:03 e fechou depois que o modelo voltou. Nesse tempo, os clientes receberam "não sei" ou foram para a fila.
- **Diagnóstico:** a parte caiu. A busca respondeu normal a tarde toda.
- **Já tentado:** o disjuntor da aula 12 já estava ligado.

## E08. Desistência ou troca

- **Pergunta (um dos casos):** "Desisti da compra. Em quantos dias eu preciso avisar?"
- **Trechos que o assistente leu:** `trocas@1#reembolso` em 1º, `trocas@2#prazo` em 2º.
- **Resposta:** "Você tem 20 dias corridos, contados da entrega, para desistir da compra."
- **Diagnóstico:** os trechos bastam; a resposta usou o prazo de troca numa pergunta de desistência, que é de 7 dias. Resposta sem suporte. É o mesmo erro da C02 da aula 10, ao contrário.
- **Já tentado:** a matriz da aula mandou pôr "só o que está nos trechos" e a C02 corrigida como exemplo no prompt. A equipe separou 10 perguntas do conjunto de referência que pedem um prazo de troca ou de desistência. Antes do prompt novo, 9 das 10 saíram com o prazo trocado. Depois, 4 das 10. As outras falhas do conjunto caíram com o mesmo prompt.

## A nova proposta do fornecedor

> "Vimos a matriz. Então fazemos assim: ajustamos um modelo menor com as conversas do atendimento de 2026 inteiro. Fica mais barato, pega o tom da loja e aprende as políticas, inclusive os prazos. Assim vocês não precisam mais dos exemplos no prompt."
