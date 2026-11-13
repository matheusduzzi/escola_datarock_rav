"""Treina o adaptador QLoRA com o treino e a validação separados pelo ajuste.py.

Caminho com placa de vídeo. Precisa de Python 3.11 ou mais novo, placa NVIDIA com CUDA e as
bibliotecas de requisitos-treino.txt. Sem placa, use o ajuste pronto da pasta ajuste-ti/.

    python3 treinar_qlora.py --checar --treino separado/treino.jsonl --validacao separado/validacao.jsonl
    python3 treinar_qlora.py --treino separado/treino.jsonl --validacao separado/validacao.jsonl --saida meu-ajuste

O --checar só lê os arquivos e mostra a configuração: roda em qualquer computador, sem instalar nada.
Sem o --checar, o programa treina, salva um checkpoint por época e grava meu-ajuste/registro-treino.csv
no formato que o ajuste.py registro lê, com o pico de memória da placa.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ajuste import Erro, carregar_politicas, carregar_prompt, ler_jsonl, mensagens  # noqa: E402

MODELO = 'Qwen/Qwen2.5-1.5B-Instruct'
LORA = {'r': 16, 'lora_alpha': 32, 'lora_dropout': 0.05, 'target_modules': 'all-linear'}
TREINO = {'epocas': 5, 'exemplos_por_passo': 4, 'taxa_de_aprendizado': 1e-4, 'max_length': 1024}


def conversas(arquivo, politicas, prompt):
    """Cada exemplo vira pedido e resposta: o treino calcula a perda só na resposta."""
    linhas = []
    for ex in ler_jsonl(arquivo):
        linhas.append({'prompt': mensagens(ex, politicas, prompt),
                       'completion': [{'role': 'assistant', 'content': ex['resposta']}]})
    if not linhas:
        raise Erro(f'{arquivo} está vazio')
    return linhas


def gravar_registro(historico, pasta):
    """Junta o loss de treino e o de validação de cada passo, como o ajuste.py registro espera."""
    por_passo = {}
    for h in historico:
        passo = h.get('step')
        if passo is None:
            continue
        linha = por_passo.setdefault(passo, {'passo': passo, 'epoca': '', 'loss_treino': '', 'loss_validacao': ''})
        if 'epoch' in h:
            linha['epoca'] = round(h['epoch'])
        if 'loss' in h:
            linha['loss_treino'] = f'{h["loss"]:.2f}'
        if 'eval_loss' in h:
            linha['loss_validacao'] = f'{h["eval_loss"]:.2f}'
    arquivo = Path(pasta) / 'registro-treino.csv'
    with arquivo.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['passo', 'epoca', 'loss_treino', 'loss_validacao', 'checkpoint'])
        for passo in sorted(por_passo):
            l = por_passo[passo]
            if l['loss_treino'] == '' and l['loss_validacao'] == '':
                continue
            ck = f'checkpoint-{passo}' if (Path(pasta) / f'checkpoint-{passo}').is_dir() else ''
            w.writerow([l['passo'], l['epoca'], l['loss_treino'], l['loss_validacao'], ck])
    return arquivo


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--treino', required=True)
    p.add_argument('--validacao', required=True)
    p.add_argument('--saida', default='meu-ajuste')
    p.add_argument('--prompt', default='curto')
    p.add_argument('--epocas', type=int, default=TREINO['epocas'])
    p.add_argument('--checar', action='store_true', help='só lê os arquivos e mostra a configuração')
    a = p.parse_args(argv)
    if a.epocas < 1:
        print('erro: --epocas precisa ser 1 ou mais', file=sys.stderr)
        return 2
    treino_cfg = dict(TREINO, epocas=a.epocas)
    try:
        politicas = carregar_politicas()
        prompt = carregar_prompt(a.prompt)
        treino = conversas(a.treino, politicas, prompt)
        validacao = conversas(a.validacao, politicas, prompt)
    except Erro as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2
    passos = -(-len(treino) // TREINO['exemplos_por_passo'])
    print(f'modelo: {MODELO}, guardado em 4 bits NF4 com dupla quantização')
    print(f'LoRA: r={LORA["r"]}, lora_alpha={LORA["lora_alpha"]}, em todas as camadas lineares')
    print(f'treino: {len(treino)} exemplos; validação: {len(validacao)} exemplos; prompt: {a.prompt}')
    print(f'{a.epocas} épocas de {passos} passos, {TREINO["exemplos_por_passo"]} exemplos por passo: '
          f'checkpoints {", ".join(str(passos * e) for e in range(1, a.epocas + 1))}')
    if a.checar:
        print('checagem: arquivos lidos, nada foi treinado')
        return 0

    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    if not torch.cuda.is_available():
        print('erro: não achei placa NVIDIA com CUDA. Faça a aula pelo ajuste pronto, em ajuste-ti/', file=sys.stderr)
        return 2
    bf16 = torch.cuda.is_bf16_supported()
    calculo = torch.bfloat16 if bf16 else torch.float16
    quantizacao = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                     bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=calculo)
    config = SFTConfig(
        output_dir=a.saida,
        num_train_epochs=a.epocas,
        per_device_train_batch_size=TREINO['exemplos_por_passo'],
        per_device_eval_batch_size=TREINO['exemplos_por_passo'],
        gradient_accumulation_steps=1,
        learning_rate=TREINO['taxa_de_aprendizado'],
        eval_strategy='epoch',
        save_strategy='epoch',
        logging_strategy='epoch',
        bf16=bf16,
        fp16=not bf16,
        max_length=TREINO['max_length'],
        model_init_kwargs={'dtype': calculo, 'device_map': {'': 0}},
        report_to='none',
    )
    trainer = SFTTrainer(
        model=MODELO,
        args=config,
        train_dataset=Dataset.from_list(treino),
        eval_dataset=Dataset.from_list(validacao),
        quantization_config=quantizacao,
        peft_config=LoraConfig(task_type='CAUSAL_LM', **LORA),
    )
    torch.cuda.reset_peak_memory_stats()
    trainer.train()
    pico = torch.cuda.max_memory_allocated() / 1e9
    registro = gravar_registro(trainer.state.log_history, a.saida)
    resumo = {'modelo': MODELO, 'lora': LORA, 'treino': treino_cfg, 'exemplos_treino': len(treino),
              'exemplos_validacao': len(validacao), 'prompt': a.prompt,
              'pico_de_memoria_gb': round(pico, 2), 'placa': torch.cuda.get_device_name(0)}
    (Path(a.saida) / 'config.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'pico de memória da placa: {pico:.2f} GB')
    print(f'registro: {registro}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
