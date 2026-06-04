Quick guide: fine-tune Qwen-style model on Vietnamese math dataset

1. Create a Python environment and install deps:

```bash
python -m venv venv
source venv/bin/activate  # on Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Example run (single-node):

```bash
python train_qwen_finetune.py \
  --data ../DATA/augmented_train_data_validated.jsonl \
  --model qwen/qwen-2.5-math-instruct-1.5b \
  --output_dir ../qwen_finetuned_math \
  --per_device_train_batch_size 2 \
  --gradient_accumulation_steps 8 \
  --num_train_epochs 3 \
  --fp16
```

3. Notes and tips
- If GPU memory is limited, use `--load_in_8bit` and optionally `--use_lora` (install `peft`).
- Enable `--force_cot` to prefix targets with a Chain-of-Thought hint.
- To use LoRA, provide `--lora_target_modules` comma-separated to match Qwen internals.
