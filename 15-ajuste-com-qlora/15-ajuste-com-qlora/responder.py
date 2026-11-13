"""Gera as respostas de uma variante no conjunto de avaliação, no formato que o ajuste.py comparar lê.

Caminho com placa de vídeo, com as mesmas bibliotecas do treinar_qlora.py.

    python3 responder.py --avaliacao separado/avaliacao.jsonl --variante base --saida minhas/base.jsonl
    python3 responder.py --avaliacao separado/avaliacao.jsonl --variante base-3-exemplos --prompt 3-exemplos \
        --saida minhas/base-3-exemplos.jsonl
    python3 responder.py --avaliacao separado/avaliacao.jsonl --variante meu-passo-24 \
        --adaptador meu-ajuste/checkpoint-24 --saida minhas/meu-passo-24.jsonl

Sem --adaptador, responde o modelo sem ajuste. A resposta sai sem sorteio (do_sample=False), para a
mesma pergunta dar a mesma resposta a cada vez que você rodar.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ajuste import Erro, carregar_politicas, carregar_prompt, ler_jsonl, mensagens  # noqa: E402
from treinar_qlora import MODELO  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--avaliacao', required=True)
    p.add_argument('--variante', required=True)
    p.add_argument('--saida', required=True)
    p.add_argument('--prompt', default='curto')
    p.add_argument('--adaptador', help='pasta de um checkpoint do treinar_qlora.py')
    p.add_argument('--max-novos', type=int, default=200)
    a = p.parse_args(argv)
    try:
        politicas = carregar_politicas()
        prompt = carregar_prompt(a.prompt)
        avaliacao = ler_jsonl(a.avaliacao)
    except Erro as e:
        print(f'erro: {e}', file=sys.stderr)
        return 2

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    if not torch.cuda.is_available():
        print('erro: não achei placa NVIDIA com CUDA', file=sys.stderr)
        return 2
    calculo = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    quantizacao = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                                     bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=calculo)
    tok = AutoTokenizer.from_pretrained(MODELO)
    modelo = AutoModelForCausalLM.from_pretrained(MODELO, quantization_config=quantizacao, dtype=calculo,
                                                  device_map={'': 0})
    if a.adaptador:
        from peft import PeftModel
        # O adaptador fica separado do modelo em 4 bits: nada de juntar (merge) antes de medir.
        modelo = PeftModel.from_pretrained(modelo, a.adaptador)
    modelo.eval()

    saida = []
    for ex in avaliacao:
        entrada = tok.apply_chat_template(mensagens(ex, politicas, prompt), add_generation_prompt=True,
                                          return_tensors='pt', return_dict=True).to(modelo.device)
        with torch.no_grad():
            gerado = modelo.generate(**entrada, max_new_tokens=a.max_novos, do_sample=False)
        texto = tok.decode(gerado[0][entrada['input_ids'].shape[1]:], skip_special_tokens=True).strip()
        saida.append({'id': ex['id'], 'variante': a.variante, 'prompt': a.prompt, 'resposta': texto})
        print(f'{ex["id"]}: {texto[:70]}')
    Path(a.saida).parent.mkdir(parents=True, exist_ok=True)
    Path(a.saida).write_text(''.join(json.dumps(l, ensure_ascii=False) + '\n' for l in saida), encoding='utf-8')
    print(f'gravado: {a.saida} ({len(saida)} respostas)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
