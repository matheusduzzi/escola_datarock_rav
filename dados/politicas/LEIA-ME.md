# Políticas da Loja Exemplo

`politicas.json` é a lista de trechos das políticas da loja que o assistente de atendimento pode usar. São 16 trechos de 6 documentos: trocas, entregas, pagamentos, garantia, exceções e financeiro. Os textos de trocas, entregas, pagamentos e garantia são os mesmos de Agentes de IA em produção. Os prazos e valores são regras da loja do curso, não orientação jurídica.

Cada trecho é um objeto com estes campos:

| Campo | O que guarda | Exemplo |
|---|---|---|
| `id` | documento, versão e seção juntos | `trocas@2#prazo` |
| `documento` | nome do documento | `trocas` |
| `secao` | seção dentro do documento | `prazo` |
| `versao` | número da versão, inteiro | `2` |
| `titulo` | título da seção | `Prazo para troca` |
| `texto` | o texto que o assistente pode citar | |
| `inicio` | primeiro dia em que a versão vale, no formato `AAAA-MM-DD` | `2026-10-01` |
| `fim` | primeiro dia em que a versão deixa de valer; `null` quando ainda vale | `null` |
| `perfis` | quem pode ler o trecho: `cliente`, `atendimento`, `supervisao` ou `financeiro` | `["cliente", "atendimento"]` |
| `status` | `aprovado` ou `rascunho` | `aprovado` |

O prazo de troca tem três versões. A versão 1 valeu até 30 de setembro de 2026, a 2 vale desde 1º de outubro e a 3 ainda é rascunho. O dia em `fim` já não faz parte da versão. Os trechos de exceções e de financeiro são internos: o perfil `cliente` não lê esses dois.

O arquivo foi escrito à mão e não muda entre execuções. A tarefa 1 do diagnóstico lê esse arquivo.
