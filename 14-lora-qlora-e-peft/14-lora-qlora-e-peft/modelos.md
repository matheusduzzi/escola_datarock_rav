# Os dois modelos do exercício

## Modelo de 1,1 bilhão: TinyLlama 1.1B

Modelo aberto, com licença Apache 2.0 no cartão do modelo. Os números saem do `config.json` do repositório `TinyLlama/TinyLlama-1.1B-Chat-v1.0` na Hugging Face, lido em 13/11/2026.

| Campo do `config.json` | Valor | O que quer dizer |
|---|---|---|
| `hidden_size` | 2048 | largura do modelo: entrada de q, k, v e o, e saída de q e o |
| `num_hidden_layers` | 22 | camadas |
| `num_attention_heads` | 32 | cabeças de atenção de q; cada uma com 2048 ÷ 32 = 64 |
| `num_key_value_heads` | 4 | cabeças de k e de v; saída de k e de v = 4 × 64 = 256 |
| `intermediate_size` | 5632 | largura da parte MLP de cada camada (não entra no exercício) |
| `vocab_size` | 32000 | tamanho do vocabulário |

Total de parâmetros, somando atenção, MLP, normalizações, a entrada e a saída do vocabulário: **1.100.048.384**.

| Matriz | Entrada | Saída |
|---|---|---|
| q | 2048 | 2048 |
| k | 2048 | 256 |
| v | 2048 | 256 |
| o | 2048 | 2048 |

## Modelo de 7 bilhões: LLaMA 7B

Números da tabela 2 do artigo "LLaMA: Open and Efficient Foundation Language Models" (Touvron e outros, 2023): **6,7 bilhões** de parâmetros, dimensão 4096, 32 cabeças e 32 camadas. As quatro matrizes de atenção têm 4096 de entrada e 4096 de saída.

O artigo do QLoRA mede **5.048 MB** para o modelo de 7 bilhões em 4 bits (seção 2, "QLoRA: Efficient Finetuning of Quantized LLMs", Dettmers e outros, 2023).
