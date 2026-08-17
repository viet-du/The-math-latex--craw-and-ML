"""
5-Agent Math Solver - Training Pipeline (Resume)
Qwen2.5-Math-1.5B-Instruct with LoRA Only
============================================================
CHỈ TRAIN agent3, agent4, agent5 (agent1, agent2 đã xong)
Giữ nguyên cấu hình từ lần train trước.
"""

# %% Cell 1: Imports & Setup
import os, sys, re, json, time, gc, random, math
from pathlib import Path

# Install dependencies
def install(pkg):
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

for pkg in [
    "transformers>=4.45.0",
    "peft>=0.13.0",
    "accelerate",
    "bitsandbytes",
    "datasets>=3.0.0",
    "scikit-learn",
    "sentencepiece",
    "matplotlib",
    "seaborn",
    "pandas",
    "numpy",
]:
    try:
        install(pkg)
    except Exception as e:
        print(f"[WARN] Failed to install {pkg}: {e}")

# Uninstall torchao to avoid PEFT version conflict
print("[INFO] Fixing peft/torchao version conflict...")
try:
    subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "-q", "torchao"])
    print("[OK] torchao uninstalled")
except Exception as e:
    print(f"[WARN] torchao uninstall failed: {e}")

try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "peft==0.14.0"])
    print("[OK] peft 0.14.0 installed (no torchao required)")
except Exception as e:
    print(f"[WARN] peft 0.14.0 install failed: {e}")

# Verify versions
try:
    import peft
    print(f"[INFO] peft version: {peft.__version__}")
except Exception as e:
    print(f"[WARN] peft check failed: {e}")

# Clear peft module cache so next import reloads
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith("peft") or "torchao" in mod_name:
        del sys.modules[mod_name]
print("[OK] peft/torchao modules cleared")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import torch
from datasets import Dataset, load_dataset, concatenate_datasets
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback,
    DataCollatorForLanguageModeling,
    TrainerCallback,
)
from peft import LoraConfig, get_peft_model, TaskType

# Monkey-patch: PEFT 0.14/0.16 both raise ImportError when torchao is too old.
try:
    import peft.import_utils as _peft_utils
    _peft_utils.is_torchao_available = lambda: False
    print("[OK] Patched peft.import_utils.is_torchao_available -> False")
except Exception as e:
    print(f"[WARN] Patch failed: {e}")

try:
    import peft.tuners.lora.torchao as _lora_tao
    _lora_tao.is_torchao_available = lambda: False
    print("[OK] Patched peft.tuners.lora.torchao.is_torchao_available -> False")
except Exception as e:
    print(f"[WARN] Lora torchao patch failed: {e}")

# Set style for matplotlib
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")
plt.rcParams['figure.dpi'] = 150
plt.rcParams['savefig.dpi'] = 150
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['axes.labelsize'] = 10

print(f"PyTorch {torch.__version__} | CUDA: {torch.cuda.is_available()}")
print(f"Matplotlib {plt.matplotlib.__version__} | Seaborn {sns.__version__}")


# Custom JSON encoder for numpy types
class NumpyEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.bool_):
            return bool(o)
        return super().default(o)


# %% Cell 2: Configuration
class CFG:
    model_name = "Qwen/Qwen2.5-Math-1.5B-Instruct"
    data_dir   = "/kaggle/input/datasets/vitduq/full-data13-08/5agent_final"
    output_dir = "/kaggle/working/outputs"
    plots_dir  = "/kaggle/working/plots"
    seed       = 42

    # Target modules for Qwen2.5 — attention Q/K/V only
    target_modules = ["q_proj", "k_proj", "v_proj"]

    # ============================================================
    # TRAINING HYPERPARAMETERS - GIỮ NGUYÊN TỪ LẦN TRƯỚC
    # ============================================================
    bf16 = True
    fp16 = False
    optim = "paged_adamw_8bit"
    max_seq_len = 1024

    # ============================================================
    # EPOCHS / STEPS - GIỮ NGUYÊN
    # ============================================================
    epochs = 4
    per_device_batch_size = 2
    grad_accum = 8              # effective batch = 16

    lr = 1e-4
    min_lr = 1e-5
    warmup_ratio = 0.05
    weight_decay = 0.0
    max_grad_norm = 1.0
    neftune_noise_alpha = 5.0
    use_gradient_checkpointing = True

    eval_steps = 25
    save_steps = 25
    save_total_limit = 4

    # ============================================================
    # CHỈ TRAIN agent3, agent4, agent5 (agent1, agent2 đã xong)
    # ============================================================
    active_agents = ["agent3", "agent4", "agent5"]

    # LoRA rank - giữ nguyên
    lora_r = {
        "agent1": 32,
        "agent2": 32,
        "agent3": 32,
        "agent4": 32,
        "agent5": 32,
    }
    lora_alpha = 64
    lora_dropout = 0.05


# Detect bf16 support
if CFG.bf16 and not torch.cuda.is_bf16_supported():
    print("[INFO] bf16 not supported on this GPU, falling back to fp16")
    CFG.bf16 = False
    CFG.fp16 = True


os.makedirs(CFG.output_dir, exist_ok=True)
os.makedirs(CFG.plots_dir, exist_ok=True)


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


seed_everything(CFG.seed)


# %% Cell 3: Data Loading Utilities
def load_jsonl(path):
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except:
                    pass
    return data


def save_jsonl(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')


def format_for_chat(record):
    """Normalize record into dict {messages: [user, assistant]}."""
    if not isinstance(record, dict):
        return record

    msgs = record.get('messages', [])
    if not msgs or not isinstance(msgs, list):
        return record

    user_msg = None
    assistant_msg = None
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = m.get('role')
        if role == 'user' and user_msg is None:
            user_msg = m
        elif role == 'assistant' and assistant_msg is None:
            assistant_msg = m

    if user_msg and isinstance(user_msg.get('content'), (str, dict)):
        content = user_msg.get('content')
        if isinstance(content, str):
            try:
                stripped = content.strip()
                if stripped.startswith('{') or stripped.startswith('['):
                    content = json.loads(stripped)
            except Exception:
                pass

        if isinstance(content, dict):
            inp_vals = content.get('input_values', content.get('input', {}))
            out_val = content.get('output', content.get('response', ''))
            solution = content.get('solution', '')
            if solution:
                assistant_text = f"{solution}\n\nFinal answer: {out_val}" if out_val else solution
            else:
                assistant_text = str(out_val)

            if isinstance(inp_vals, dict) and inp_vals:
                prompt_parts = []
                for k, v in inp_vals.items():
                    prompt_parts.append(f"{k}: {v}")
                prompt = "\n".join(prompt_parts)
            else:
                prompt = str(inp_vals) if inp_vals else "Solve this problem."
            user_msg = {"role": "user", "content": prompt}
            assistant_msg = {"role": "assistant", "content": str(assistant_text)}

    if user_msg and assistant_msg:
        new_record = dict(record)
        new_record['messages'] = [user_msg, assistant_msg]
        return new_record

    return record


# %% Cell 4: EDA (compact version - skip vì đã có từ lần trước)
print("\n" + "=" * 70)
print("STEP 1: DATA LOADING (Skip EDA - đã có từ lần train trước)")
print("=" * 70)

# Shared data-layout resolver
def _resolve_data_dir():
    candidate_dirs = [
        CFG.data_dir,
        "/kaggle/input/datasets/vitduq/datasheet-full05082026/5agent_final",
        "/kaggle/input/datasheet-full05082026/5agent_final",
        "/kaggle/input/5agent_final",
        "/kaggle/input/datasets/vitduq/5agent_final",
        "/kaggle/working/data/5agent_final",
        "/kaggle/working/5agent_final",
        "/kaggle/working/DATA/5agent_final",
    ]
    for cand in candidate_dirs:
        if (cand and os.path.exists(os.path.join(cand, "train", "agent1.jsonl"))
                and os.path.exists(os.path.join(cand, "test", "agent1.jsonl"))):
            return cand, "A"
    for cand in candidate_dirs:
        if cand and os.path.exists(os.path.join(cand, "agent1.jsonl")):
            return cand, "B"
    return None, None

def _agent_file(agent_id, kind="train"):
    base, layout = _DATA_LAYOUT
    if base is None:
        return None
    if layout == "A":
        return os.path.join(base, kind, f"{agent_id}.jsonl")
    cand_dir = base
    if not os.path.isdir(cand_dir):
        return None
    try:
        files = [f for f in os.listdir(cand_dir) if f.startswith(f"{agent_id}") and f.endswith(".jsonl")]
    except OSError:
        return None
    if not files:
        return None
    prefer_keyword = "train" if kind == "train" else "test"
    preferred = sorted([f for f in files if prefer_keyword in f.lower()])
    chosen = preferred[0] if preferred else sorted(files)[0]
    return os.path.join(cand_dir, chosen)

_DATA_LAYOUT = _resolve_data_dir()
_resolved_dir, _layout = _DATA_LAYOUT
if _resolved_dir is not None:
    print(f"[INFO] Data dir: {_resolved_dir}  (layout={_layout})")
    if _resolved_dir != CFG.data_dir:
        CFG.data_dir = _resolved_dir
        print(f"[INFO] CFG.data_dir updated to: {CFG.data_dir}")
else:
    print(f"[WARN] No data dir resolved. Falling back to: {CFG.data_dir}")
    _layout = "A"

# Quick stats cho 3 agents còn lại
for agent_id in CFG.active_agents:
    print(f"\n[DATA] {agent_id.upper()}")
    train_file = _agent_file(agent_id, "train")
    test_file  = _agent_file(agent_id, "test")

    if not train_file or not os.path.exists(train_file):
        print(f"   [WARN] No data file found for {agent_id}")
        continue

    train_data = load_jsonl(train_file)
    test_data = load_jsonl(test_file) if (test_file and os.path.exists(test_file)) else []
    print(f"   Train: {len(train_data)} | Test: {len(test_data)}")


# %% Cell 5: Tokenize Dataset
print("\n" + "=" * 70)
print("STEP 2: TOKENIZE DATASET (agent3, agent4, agent5)")
print("=" * 70)

print(f"\n[TOKENIZE] Loading tokenizer: {CFG.model_name}")
tokenizer = AutoTokenizer.from_pretrained(CFG.model_name, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token


def tokenize_fn(example, max_length=CFG.max_seq_len):
    """Tokenize one chat example; mask labels on prompt + pad tokens."""
    messages = example.get('messages', [])

    if isinstance(messages, str):
        try:
            messages = json.loads(messages) if messages.startswith('[') else [{"role": "user", "content": messages}]
        except Exception:
            messages = [{"role": "user", "content": messages}]

    use_assistant_mask = False
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*generation.*")
        warnings.filterwarnings("ignore", message=".*assistant_tokens_mask.*")
        try:
            chat = tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=False,
                return_assistant_tokens_mask=True,
                return_dict=True,
            )
            prompt_ids = list(chat["input_ids"])
            raw_asm = list(chat.get("assistant_masks") or [0] * len(prompt_ids))
            if any(raw_asm):
                assistant_mask = raw_asm
                use_assistant_mask = True
            else:
                assistant_mask = None
        except (TypeError, ValueError, Exception):
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False,
            )
            prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            prompt_ids = list(prompt_ids)
            assistant_mask = None

    if not use_assistant_mask or assistant_mask is None:
        try:
            prompt_only = tokenizer.apply_chat_template(
                messages[:-1], tokenize=False, add_generation_prompt=True,
            )
            prompt_len = len(tokenizer(prompt_only, add_special_tokens=False)["input_ids"])
            assistant_mask = [0] * len(prompt_ids)
            for i in range(prompt_len, len(assistant_mask)):
                assistant_mask[i] = 1
            if any(assistant_mask):
                use_assistant_mask = True
        except Exception:
            assistant_mask = None
            use_assistant_mask = False

    if len(prompt_ids) > max_length:
        prompt_ids = prompt_ids[:max_length]
        if assistant_mask is not None:
            assistant_mask = assistant_mask[:max_length]
        attention_mask = [1] * max_length
    else:
        attention_mask = [1] * len(prompt_ids)
        pad_len = max_length - len(prompt_ids)
        prompt_ids = prompt_ids + [tokenizer.pad_token_id] * pad_len
        attention_mask = attention_mask + [0] * pad_len
        if assistant_mask is not None:
            assistant_mask = assistant_mask + [0] * pad_len

    result = {
        "input_ids": prompt_ids,
        "attention_mask": attention_mask,
    }
    labels = list(prompt_ids)
    labels = [(-100 if m == 0 else v) for v, m in zip(labels, attention_mask)]
    if use_assistant_mask and assistant_mask is not None:
        labels = [(-100 if m == 0 else v) for v, m in zip(labels, assistant_mask)]

    result["labels"] = labels
    return result


tokenized_datasets = {}

for agent_id in CFG.active_agents:
    print(f"\n[TOKENIZE] Processing {agent_id}...")

    train_file = _agent_file(agent_id, "train")
    test_file  = _agent_file(agent_id, "test")

    if not train_file or not os.path.exists(train_file):
        print(f"[WARN] Skipping {agent_id} (no train file)")
        continue

    train_data = load_jsonl(train_file)
    test_data  = load_jsonl(test_file) if (test_file and os.path.exists(test_file)) else []

    train_data = [format_for_chat(d) if isinstance(d, dict) else d for d in train_data]
    test_data  = [format_for_chat(d) if isinstance(d, dict) else d for d in test_data]

    def is_valid(record):
        if not isinstance(record, dict):
            return False
        msgs = record.get('messages')
        if not msgs or not isinstance(msgs, list) or len(msgs) < 2:
            return False
        for m in msgs:
            if not isinstance(m, dict):
                return False
            c = m.get('content')
            if not c or not isinstance(c, str):
                return False
        return True

    train_data = [r for r in train_data if is_valid(r)]
    test_data  = [r for r in test_data  if is_valid(r)]
    print(f"   After filter: Train: {len(train_data)}, Test: {len(test_data)}")

    if not train_data:
        print(f"   [WARN] No valid samples for {agent_id}, skipping")
        continue

    train_ds = Dataset.from_list(train_data)
    test_ds  = Dataset.from_list(test_data) if test_data else None

    train_tokenized = train_ds.map(
        tokenize_fn,
        remove_columns=train_ds.column_names,
        desc=f"Tokenizing {agent_id} train",
    )

    test_tokenized = None
    if test_ds and len(test_ds) > 0:
        test_tokenized = test_ds.map(
            tokenize_fn,
            remove_columns=test_ds.column_names,
            desc=f"Tokenizing {agent_id} test",
        )

    if test_tokenized is None or len(test_tokenized) == 0:
        print(f"   [WARN] {agent_id}: test split empty, falling back to train split for eval")
        test_tokenized = train_tokenized
    do_eval = len(test_tokenized) > 0

    tokenized_datasets[agent_id] = {
        'train': train_tokenized,
        'test': test_tokenized,
        'num_train': len(train_tokenized),
        'num_test': len(test_tokenized),
        'do_eval': do_eval,
    }
    print(f"   [OK] {agent_id}: {len(train_tokenized)} train, {len(test_tokenized)} test")


# %% Cell 6: Custom collator
class DataCollatorForCausalLM:
    """Pad input_ids/attention_mask/labels to the longest sequence in the batch."""
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer
        self.pad_id = tokenizer.pad_token_id

    def __call__(self, features):
        max_len = max(len(f["input_ids"]) for f in features)
        input_ids, attn, labels = [], [], []
        for f in features:
            n = max_len - len(f["input_ids"])
            input_ids.append(list(f["input_ids"]) + [self.pad_id] * n)
            attn.append(list(f["attention_mask"]) + [0] * n)
            labels.append(list(f["labels"]) + [-100] * n)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attn, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


# %% Cell 7: Custom callback
class LRLogger(TrainerCallback):
    pass


# %% Cell 8: Training Loop - CHỈ agent3, agent4, agent5
print("\n" + "=" * 70)
print("STEP 3: TRAINING 3 AGENTS (agent3, agent4, agent5)")
print("=" * 70)
print("[INFO] agent1, agent2 đã train xong - SKIP")
print(f"[INFO] Training agents: {CFG.active_agents}")
print(f"[INFO] Config giữ nguyên từ lần train trước")
print(f"       - Epochs: {CFG.epochs}")
print(f"       - Effective batch: {CFG.per_device_batch_size * CFG.grad_accum}")
print(f"       - LR: {CFG.lr} -> {CFG.min_lr}")
print(f"       - LoRA rank/alpha: 32 / {CFG.lora_alpha}")
print(f"       - NEFTune: {CFG.neftune_noise_alpha}")
print("=" * 70)

training_history = {}
df_rows = []

for agent_id in CFG.active_agents:
    if agent_id not in tokenized_datasets:
        continue

    lora_rank = CFG.lora_r.get(agent_id, 32)
    agent_output_dir = os.path.join(CFG.output_dir, agent_id)

    print(f"\n{'='*70}")
    print(f"[TRAIN] {agent_id.upper()} (LoRA r={lora_rank}, alpha={CFG.lora_alpha}, lr={CFG.lr} -> {CFG.min_lr})")
    print(f"{'='*70}")

    t0 = time.time()

    # Load base model
    print(f"   [LOAD] Loading base model...")
    model = AutoModelForCausalLM.from_pretrained(
        CFG.model_name,
        torch_dtype=torch.bfloat16 if CFG.bf16 else torch.float16,
        device_map="auto",
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )

    # Freeze all params
    print(f"   [FREEZE] Freezing base model parameters...")
    for name, param in model.named_parameters():
        param.requires_grad = False
    frozen_params = sum(p.numel() for p in model.parameters() if not p.requires_grad)
    total_params  = sum(p.numel() for p in model.parameters())
    print(f"   [INFO] Frozen params: {frozen_params:,} / {total_params:,} ({100*frozen_params/total_params:.1f}%)")

    # LoRA config
    print(f"   [CONFIG] Setting up LoRA adapter...")
    lora_config = LoraConfig(
        r=lora_rank,
        lora_alpha=CFG.lora_alpha,
        target_modules=CFG.target_modules,
        lora_dropout=CFG.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    all_param        = sum(p.numel() for p in model.parameters())
    print(f"   [VERIFY] Trainable params: {trainable_params:,} / {all_param:,} ({100*trainable_params/all_param:.3f}%)")
    model.print_trainable_parameters()

    # Sanity check
    for name, param in model.named_parameters():
        if "lora" not in name.lower() and param.requires_grad:
            raise ValueError(f"Base model parameter {name} is trainable!")

    # Enable NEFTune
    if CFG.neftune_noise_alpha is not None and CFG.neftune_noise_alpha > 0:
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
        else:
            for p in model.get_input_embeddings().parameters():
                p.requires_grad = True

    # Data
    ds = tokenized_datasets[agent_id]
    train_ds = ds['train']
    eval_ds  = ds['test']
    do_eval  = ds.get('do_eval', len(eval_ds) > 0)

    # Training arguments
    steps_per_epoch = max(1, len(train_ds) // (CFG.per_device_batch_size * CFG.grad_accum))
    total_steps     = steps_per_epoch * CFG.epochs
    warmup_steps    = max(1, int(CFG.warmup_ratio * total_steps))

    import inspect
    from transformers import TrainingArguments as _TA
    _TA_SUPPORTED = set(inspect.signature(_TA.__init__).parameters.keys())

    _ta_kwargs = dict(
        output_dir=agent_output_dir,
        num_train_epochs=CFG.epochs,
        per_device_train_batch_size=CFG.per_device_batch_size,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=CFG.grad_accum,
        learning_rate=CFG.lr,
        weight_decay=CFG.weight_decay,
        optim=CFG.optim,
        bf16=CFG.bf16,
        fp16=CFG.fp16,
        max_grad_norm=CFG.max_grad_norm,
        neftune_noise_alpha=CFG.neftune_noise_alpha if CFG.neftune_noise_alpha else None,
        lr_scheduler_type="cosine_with_min_lr",
        lr_scheduler_kwargs={"min_lr": CFG.min_lr},
        warmup_steps=warmup_steps,
        gradient_checkpointing=CFG.use_gradient_checkpointing,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=5,
        logging_first_step=True,
        logging_strategy="steps",
        disable_tqdm=False,
        log_level="info",
        report_to="none",
        save_strategy="steps" if do_eval else "no",
        save_steps=CFG.save_steps if do_eval else 0,
        save_total_limit=CFG.save_total_limit,
        eval_strategy="steps" if do_eval else "no",
        eval_steps=CFG.eval_steps if do_eval else 0,
        eval_accumulation_steps=1,
        load_best_model_at_end=True if do_eval else False,
        metric_for_best_model="eval_loss" if do_eval else None,
        greater_is_better=False,
        seed=CFG.seed,
        remove_unused_columns=False,
        dataloader_num_workers=0,
        dataloader_pin_memory=True,
        past_index=-1,
    )

    _dropped = [k for k in list(_ta_kwargs) if k not in _TA_SUPPORTED and _ta_kwargs[k] is not None]
    _ta_kwargs = {k: v for k, v in _ta_kwargs.items() if k in _TA_SUPPORTED}
    if _dropped:
        try:
            from importlib.metadata import version as _v
            _hf_ver = _v("transformers")
        except Exception:
            _hf_ver = "?"
        print(f"   [INFO] transformers {_hf_ver} dropped unsupported args: {_dropped}")

    training_args = TrainingArguments(**_ta_kwargs)

    print(f"   [INFO] Steps/epoch: {steps_per_epoch} | Total: {total_steps} | Warmup: {warmup_steps}")
    print(f"   [INFO] LR scheduler: cosine_with_min_lr ({CFG.lr} -> {CFG.min_lr})")
    print(f"   [INFO] Eval every {CFG.eval_steps} steps; save best + last {CFG.save_total_limit}")

    _trainer_kwargs = dict(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds if do_eval else None,
        data_collator=DataCollatorForCausalLM(tokenizer),
        callbacks=([EarlyStoppingCallback(early_stopping_patience=5), LRLogger()] if do_eval else [LRLogger()]),
    )
    if "processing_class" in inspect.signature(Trainer.__init__).parameters:
        _trainer_kwargs["processing_class"] = tokenizer
    elif "tokenizer" in inspect.signature(Trainer.__init__).parameters:
        _trainer_kwargs["tokenizer"] = tokenizer

    trainer = Trainer(**_trainer_kwargs)

    # Train
    print(f"   [START] Starting training...")
    trainer.train()

    # Save final adapter
    trainer.save_model(agent_output_dir)
    print(f"   [SAVE] Adapter saved: {agent_output_dir}")

    adapter_config = {
        "base_model_name": CFG.model_name,
        "lora_rank": lora_rank,
        "lora_alpha": CFG.lora_alpha,
        "target_modules": CFG.target_modules,
        "learning_rate": CFG.lr,
        "min_lr": CFG.min_lr,
        "epochs": CFG.epochs,
        "effective_batch_size": CFG.per_device_batch_size * CFG.grad_accum,
        "neftune_noise_alpha": CFG.neftune_noise_alpha,
        "trainable_params": trainable_params,
        "total_params": all_param,
        "trainable_ratio": f"{100*trainable_params/all_param:.4f}%",
    }
    with open(os.path.join(agent_output_dir, "adapter_config.json"), 'w') as f:
        json.dump(adapter_config, f, indent=2)

    # History
    history = trainer.state
    log_history = getattr(history, "log_history", []) or []

    train_loss_logs = [e for e in log_history if "loss" in e and "eval_loss" not in e]
    eval_loss_logs  = [e for e in log_history if "eval_loss" in e]
    train_loss_final = train_loss_logs[-1]["loss"] if train_loss_logs else None
    eval_loss_final  = eval_loss_logs[-1]["eval_loss"] if eval_loss_logs else None
    train_time_min   = (time.time() - t0) / 60

    lr_log = []
    for e in train_loss_logs:
        if "learning_rate" in e:
            lr_log.append(e["learning_rate"])
    if not lr_log:
        def cosine_with_min_lr(step):
            if step < warmup_steps:
                return CFG.lr * (step / max(1, warmup_steps))
            progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
            return CFG.min_lr + 0.5 * (CFG.lr - CFG.min_lr) * (1 + math.cos(math.pi * min(1.0, progress)))
        lr_log = [cosine_with_min_lr(i) for i in range(1, total_steps + 1, max(1, total_steps // 50))]

    best_eval = min(e["eval_loss"] for e in eval_loss_logs) if eval_loss_logs else None

    training_history[agent_id] = {
        'train_loss':        [e["loss"] for e in train_loss_logs],
        'eval_loss':         [e["eval_loss"] for e in eval_loss_logs],
        'eval_steps':        [e.get("step", i) for i, e in enumerate(eval_loss_logs)],
        'learning_rate':     lr_log,
        'train_time_min':    train_time_min,
        'final_train_loss':  train_loss_final,
        'final_eval_loss':   eval_loss_final,
        'best_eval_loss':    best_eval,
        'trainable_params':  trainable_params,
        'total_params':      all_param,
    }

    df_rows.append({
        'agent': agent_id,
        'lora_rank': lora_rank,
        'trainable_params': trainable_params,
        'total_params': all_param,
        'train_samples': ds['num_train'],
        'final_train_loss': train_loss_final,
        'final_eval_loss': eval_loss_final,
        'best_eval_loss': best_eval,
        'train_time_min': train_time_min,
    })

    print(f"\n   [SUMMARY] {agent_id.upper()}")
    print(f"   Time: {train_time_min:.1f} min")
    print(f"   Final train loss: {train_loss_final:.6f}")
    if eval_loss_final is not None:
        print(f"   Final eval loss:  {eval_loss_final:.6f}")
    if best_eval is not None:
        print(f"   Best  eval loss:  {best_eval:.6f}")
    print(f"   Trainable: {trainable_params:,} / {all_param:,} ({100*trainable_params/all_param:.3f}%)")

    del model, trainer, lora_config
    gc.collect()
    torch.cuda.empty_cache()


# %% Cell 9: Training History Visualization
print("\n" + "=" * 70)
print("STEP 4: TRAINING HISTORY VISUALIZATION")
print("=" * 70)

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Training History (agent3, agent4, agent5)', fontsize=16, fontweight='bold')

colors_line = plt.cm.tab10(np.linspace(0, 1, len(training_history)))

# Plot 1: Train loss
ax1 = axes[0, 0]
for i, (agent, hist) in enumerate(training_history.items()):
    if hist['train_loss']:
        steps = range(1, len(hist['train_loss']) + 1)
        ax1.plot(steps, hist['train_loss'], label=agent, color=colors_line[i], linewidth=2)
ax1.set_xlabel('Step'); ax1.set_ylabel('Train Loss'); ax1.set_title('Training Loss per Agent')
ax1.legend(); ax1.grid(True, alpha=0.3)

# Plot 2: Eval loss
ax2 = axes[0, 1]
has_eval = False
for i, (agent, hist) in enumerate(training_history.items()):
    if hist['eval_loss']:
        has_eval = True
        ax2.plot(hist['eval_steps'], hist['eval_loss'], label=agent,
                 color=colors_line[i], linewidth=2, marker='o')
if has_eval:
    ax2.set_xlabel('Step'); ax2.set_ylabel('Eval Loss'); ax2.set_title('Evaluation Loss per Agent')
    ax2.legend(); ax2.grid(True, alpha=0.3)
else:
    ax2.text(0.5, 0.5, 'No eval data', ha='center', va='center', transform=ax2.transAxes)

# Plot 3: Learning rate
ax3 = axes[1, 0]
for i, (agent, hist) in enumerate(training_history.items()):
    if hist['learning_rate']:
        steps = range(1, len(hist['learning_rate']) + 1)
        ax3.plot(steps, hist['learning_rate'], label=agent, color=colors_line[i], linewidth=2)
if CFG.min_lr > 0:
    ax3.axhline(CFG.min_lr, color='red', linestyle='--', alpha=0.5, label=f'min_lr = {CFG.min_lr:g}')
ax3.set_xlabel('Step'); ax3.set_ylabel('Learning Rate')
ax3.set_title('Learning Rate Schedule'); ax3.legend()
ax3.grid(True, alpha=0.3); ax3.set_yscale('log')

# Plot 4: Training time
ax4 = axes[1, 1]
agents_list = list(training_history.keys())
times = [training_history[a]['train_time_min'] for a in agents_list]
bars = ax4.bar(agents_list, times, color=plt.cm.viridis(np.linspace(0.2, 0.8, len(agents_list))),
               edgecolor='white')
ax4.set_ylabel('Time (minutes)'); ax4.set_title('Training Time per Agent')
for bar, t in zip(bars, times):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f'{t:.1f}m',
             ha='center', va='bottom', fontsize=9)

plt.tight_layout()
hist_fig_path = os.path.join(CFG.plots_dir, '03_training_history.png')
fig.savefig(hist_fig_path, bbox_inches='tight', facecolor='white')
print(f"\n[OK] Training history saved: {hist_fig_path}")
plt.show()


# %% Cell 10: Summary Dashboard (bao gồm agent1, 2 đã train trước)
print("\n" + "=" * 70)
print("STEP 5: SUMMARY DASHBOARD (ALL 5 AGENTS)")
print("=" * 70)

# Load previous results if exist
prev_summary_path = os.path.join(CFG.output_dir, 'training_summary.csv')
all_df_rows = df_rows.copy()

# Thêm agent1, agent2 vào summary nếu có data
for agent_id in ["agent1", "agent2"]:
    agent_dir = os.path.join(CFG.output_dir, agent_id)
    adapter_config_path = os.path.join(agent_dir, "adapter_config.json")
    if os.path.exists(adapter_config_path):
        try:
            with open(adapter_config_path, 'r') as f:
                cfg_data = json.load(f)
            # Check checkpoint count
            checkpoints = [d for d in os.listdir(agent_dir) if d.startswith("checkpoint-")]
            is_complete = len(checkpoints) >= 3  # 4 epochs = checkpoint-75, -150, -225, -300
            
            all_df_rows.append({
                'agent': agent_id,
                'lora_rank': cfg_data.get('lora_rank', 32),
                'trainable_params': cfg_data.get('trainable_params', 0),
                'total_params': cfg_data.get('total_params', 0),
                'train_samples': 1188,  # approximate
                'final_train_loss': None,  # đã train xong, ko có log mới
                'final_eval_loss': None,
                'best_eval_loss': None,
                'train_time_min': None,
                'status': 'complete' if is_complete else 'incomplete'
            })
            print(f"[INFO] Added {agent_id} to summary (status: {'complete' if is_complete else 'incomplete'})")
        except Exception as e:
            print(f"[WARN] Could not load {agent_id} config: {e}")

df_summary = pd.DataFrame(all_df_rows)
print("\n[TRAINING SUMMARY]")
if df_summary.empty:
    print("(No training results)")
else:
    print(df_summary.to_string(index=False))

    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('Training Summary Dashboard (All 5 Agents)', fontsize=16, fontweight='bold')

    agents_list = df_summary['agent'].tolist()
    colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(agents_list)))

    # Final train loss
    ax1 = axes[0, 0]
    loss_vals = df_summary['final_train_loss'].fillna(0)
    bars = ax1.bar(agents_list, loss_vals, color=colors, edgecolor='white')
    ax1.set_ylabel('Final Train Loss'); ax1.set_title('Final Train Loss')
    for bar, l in zip(bars, loss_vals):
        if l > 0:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                     f'{l:.4f}', ha='center', va='bottom', fontsize=9)

    # Best eval loss
    ax2 = axes[0, 1]
    eval_vals = df_summary['best_eval_loss'].fillna(df_summary['final_eval_loss']).fillna(0)
    bars = ax2.bar(agents_list, eval_vals, color=colors, edgecolor='white')
    ax2.set_ylabel('Best Eval Loss'); ax2.set_title('Best Eval Loss')

    # Training time
    ax3 = axes[0, 2]
    time_vals = df_summary['train_time_min'].fillna(0)
    bars = ax3.bar(agents_list, time_vals, color='#3498db', edgecolor='white')
    ax3.set_ylabel('Time (minutes)'); ax3.set_title('Training Time')
    for bar, t in zip(bars, time_vals):
        if t > 0:
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                     f'{t:.1f}m', ha='center', va='bottom', fontsize=9)

    # Trainable param %
    ax4 = axes[1, 0]
    trainable_pcts = [100*t/total if total > 0 else 0 for t, total in 
                      zip(df_summary['trainable_params'], df_summary['total_params'])]
    bars = ax4.bar(agents_list, trainable_pcts, color='#2ecc71', edgecolor='white')
    ax4.set_ylabel('Trainable Params (%)'); ax4.set_title('LoRA Efficiency')
    ax4.set_ylim(0, max(trainable_pcts) * 1.2 if trainable_pcts else 1)
    for bar, p in zip(bars, trainable_pcts):
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                 f'{p:.3f}%', ha='center', va='bottom', fontsize=8)

    # LoRA rank distribution
    ax5 = axes[1, 1]
    rank_counts = {}
    for a, r in zip(agents_list, df_summary['lora_rank']):
        rank_counts[int(r)] = rank_counts.get(int(r), 0) + 1
    if rank_counts:
        ax5.pie(list(rank_counts.values()),
                labels=[f'r={r}' for r in rank_counts.keys()],
                autopct='%1.0f%%',
                colors=plt.cm.Set2(np.linspace(0, 1, len(rank_counts))))
    ax5.set_title('LoRA Rank Distribution')

    # Train samples
    ax6 = axes[1, 2]
    samples = df_summary['train_samples'].fillna(0)
    bars = ax6.bar(agents_list, samples, color='#9b59b6', edgecolor='white')
    ax6.set_ylabel('Train Samples'); ax6.set_title('Training Data per Agent')
    for bar, s in zip(bars, samples):
        if s > 0:
            ax6.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                     f'{int(s)}', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    summary_fig_path = os.path.join(CFG.plots_dir, '04_training_summary.png')
    fig.savefig(summary_fig_path, bbox_inches='tight', facecolor='white')
    print(f"\n[OK] Summary dashboard saved: {summary_fig_path}")
    plt.show()


# %% Cell 11: Save all results
print("\n" + "=" * 70)
print("STEP 6: SAVING ALL RESULTS")
print("=" * 70)

# Append to existing training history
existing_history = {}
history_path = os.path.join(CFG.output_dir, 'training_history.json')
if os.path.exists(history_path):
    try:
        with open(history_path, 'r') as f:
            existing_history = json.load(f)
    except:
        pass

# Merge new history with existing
existing_history.update(training_history)
with open(history_path, 'w') as f:
    json.dump(existing_history, f, indent=2, cls=NumpyEncoder)

df_summary.to_csv(summary_fig_path.replace('.png', '.csv').replace(CFG.plots_dir, CFG.output_dir), index=False)

print("\n[SAVED FILES]")
print(f"   - {CFG.output_dir}/training_history.json (updated)")
print(f"   - {CFG.plots_dir}/03_training_history.png")
print(f"   - {CFG.plots_dir}/04_training_summary.png")

print("\n" + "=" * 70)
print("TRAINING PIPELINE COMPLETED!")
print("=" * 70)
print(f"\n[RESULT] Trained agents: {list(training_history.keys())}")
print("[RESULT] agent1, agent2 đã train từ lần trước")
print("\n[TỔNG KẾT TẤT CẢ 5 AGENTS]")
print("=" * 70)
for agent_id in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
    agent_dir = os.path.join(CFG.output_dir, agent_id)
    adapter_file = os.path.join(agent_dir, "adapter_model.safetensors")
    if os.path.exists(adapter_file):
        size_mb = os.path.getsize(adapter_file) / (1024 * 1024)
        print(f"   ✅ {agent_id}: adapter_model.safetensors ({size_mb:.1f} MB)")
    else:
        print(f"   ❌ {agent_id}: CHƯA TRAIN / CHƯA CÓ WEIGHTS")
print("=" * 70)
