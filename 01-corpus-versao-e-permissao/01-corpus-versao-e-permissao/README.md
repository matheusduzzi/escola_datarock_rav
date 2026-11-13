# 01. Corpus, versão e permissão

Os arquivos da aula. Rode os comandos de dentro dessa pasta. O programa lê as políticas em `dados/politicas/politicas.json`, na raiz do kit, e só usa a biblioteca padrão do Python 3.9 ou mais novo. No Windows, troque `python3` por `py`.

| Arquivo | O que é |
|---|---|
| `corpus.py` | Mostra o que um perfil lê num dia (`ver`), as versões de uma seção no tempo (`linha`) e o que um lote de atualização muda (`lote`). |
| `lote-duplicidade.json` | O primeiro pedido do financeiro para dezembro, usado na aula. |
| `lote-duplicidade-2.json` | A segunda tentativa do financeiro, da prática guiada. |
| `lote-duplicidade-certo.json` | O mesmo pedido do jeito certo, para comparar na prática guiada. |
| `atualizacao-dezembro.json` | O lote de dezembro do exercício, com os cinco pedidos das áreas. |
| `contrato-corpus.md` | O modelo do contrato que você entrega no exercício. |

Nenhum comando muda o arquivo das políticas. Com `--lote`, o programa mostra como o corpus ficaria depois do lote: um trecho do lote com o mesmo id de um trecho que já existe toma o lugar dele.

## Comandos da aula

```bash
python3 corpus.py ver --perfil cliente --data 2026-11-10
python3 corpus.py linha trocas#prazo
python3 corpus.py lote lote-duplicidade.json
python3 corpus.py linha pagamentos#duplicidade --lote lote-duplicidade.json
python3 corpus.py ver --perfil cliente --data 2026-12-02 --lote lote-duplicidade.json
```

| Comando | O que mostra |
|---|---|
| `ver --perfil P --data AAAA-MM-DD` | os trechos que o perfil lê nesse dia e, para cada um que fica de fora, o motivo: rascunho, perfil, versão que ainda não começou ou que já acabou |
| `linha documento#secao` | as versões da seção em ordem, com o intervalo `[início, fim)`, o status e quem lê; avisa buraco e sobreposição entre as versões aprovadas |
| `lote arquivo.json` | cada trecho do lote: novo, ou o que muda num id que já existe |

Os perfis são `cliente`, `atendimento`, `supervisao` e `financeiro`. Se o terminal reclamar do `#` na seção, ponha a seção entre aspas.

## Quando o programa para

- **Código 1**, só no `ver`: duas versões aprovadas da mesma seção valem no mesmo dia. O programa lista o que o perfil leria, marca as seções em conflito com `!` e diz que o assistente não responde com esse corpus nesse dia. Corrija as datas do lote e rode de novo.
- **Código 2**, com `erro:`: falta algo ou algo está no formato errado. Por exemplo: JSON quebrado, lote sem a lista `trechos`, trecho sem algum dos dez campos, id que não é `documento@versao#secao`, `fim` igual ou antes do `inicio`, status que não é `aprovado` nem `rascunho`, perfil que não existe, data fora do formato, seção que não existe ou id repetido no lote. Leia a mensagem, corrija a entrada e rode de novo.

Código 0 não quer dizer que o lote segue o contrato. O programa olha datas, status e formato. Quem lê cada trecho e o que o texto diz, quem olha é você.

## Se precisar de ajuda

Deixe um comentário na aula. Conte o objetivo, o comando que você rodou, a saída que apareceu e o que já tentou, sem dados pessoais.
