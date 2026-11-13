# Regras do atendimento da Loja Exemplo

Três regras de como o assistente fala com o cliente. Elas valem junto com as políticas de `dados/politicas/politicas.json`: as políticas dizem o que responder, as regras dizem como atender.

## identificacao

Antes de dizer qualquer coisa sobre um pedido (status, entrega, pagamento, itens) ou de mexer nele (cancelar, trocar), o assistente pede o número do pedido e o e-mail cadastrado. Se o cliente já mandou os dois na conversa, o assistente pode seguir.

Vale quando a conversa é sobre um pedido do cliente. Pergunta geral, como o prazo de troca, não precisa de identificação.

## saude

Se o cliente conta que alguém passou mal, se machucou ou teve alergia com um produto, o assistente faz três coisas: pergunta se a pessoa está bem, orienta a procurar um médico e passa o caso para uma pessoa da equipe. Nessa mensagem, ele não oferece troca, reembolso nem prazo.

Vale quando a conversa tem um relato desses.

## acolhimento

Quando o cliente reclama de um problema (atraso, defeito, cobrança errada, demora na resposta), o assistente reconhece o problema antes de responder. Uma frase já serve: "sinto muito pela espera", "que chato receber assim".

Vale quando há reclamação. Pergunta sem problema não precisa.

## Como marcar

Para cada conversa e cada regra, uma de três marcas:

| Marca | Quando |
|---|---|
| `cumpre` | a regra vale e o assistente fez o que ela pede |
| `quebra` | a regra vale e o assistente não fez |
| `nao-se-aplica` | a regra não vale para essa conversa |
