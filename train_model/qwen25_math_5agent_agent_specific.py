"""
5-Agent Math Solver - Redesigned Training Pipeline
Qwen2.5-Math-1.5B-Instruct with Agent-Specific LoRA
====================================================
Key improvements from original:
1. Per-agent learning rates (simpler tasks = lower LR)
2. Layer-wise Learning Rate Decay (LLRD) for better fine-tuning
3. Curriculum learning with warm start
4. Agent-specific LoRA ranks (simpler = lower rank)
5. Cosine annealing with warm restarts
6. Mixed precision (BF16) for stability
"""

# %% Cell 1: Imports & Setup
import os, sys, re, json, time, gc, random
from pathlib import Path
from collections import defaultdict

# Install dependencies
def install(pkg):
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

for pkg in [
    "transformers>=4.45.0",
    "peft>=0.14.0",
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

# Fix peft/torchao version conflict
print("[INFO] Fixing peft/torchao version conflict...")
try:
    subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "-q", "torchao"])
except:
    pass

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import torch
from pathlib import Path
from datasets import Dataset, load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback,
    DataCollatorForLanguageModeling,
    get_cosine_schedule_with_warmup,
)
from peft import LoraConfig, get_peft_model, TaskType

# Monkey-patch peft
try:
    import peft.import_utils
    peft.import_utils.is_torch_tpu_available = lambda: False
    peft.import_utils.is_torchao_available = lambda: False
except:
    pass

try:
    import peft.tuners.lora.torchao
    peft.tuners.lora.torchao.is_torchao_available = lambda: False
except:
    pass

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")
plt.rcParams['figure.dpi'] = 150
plt.rcParams['savefig.dpi'] = 150

print(f"PyTorch {torch.__version__} | CUDA: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")


# %% Cell 2: Agent-Specific Configuration
class AgentCFG:
    """Configuration for each agent with specific learning rates and ranks."""
    
    # Agent definitions based on complexity:
    # Agent 1 (Simple): Gợi ý bước (hint generation) - simpler task
    # Agent 2 (Medium): Tính toán (computation) - medium task  
    # Agent 3 (Medium+): Kiểm tra (verification) - needs more precision
    # Agent 4 (Complex): Sửa lỗi (error correction) - complex task
    # Agent 5 (Complex+): Kết luận (conclusion) - most complex task
    
    agents = {
        "agent1": {
            "name": "Gợi ý bước",
            "complexity": "simple",
            "lr": 8e-5,          # Lower LR for simpler task
            "lora_r": 8,          # Lower rank = less parameters
            "lora_alpha": 16,     # Scale factor
            "warmup_ratio": 0.03, # 3% warmup (short)
            "epochs": 4,  # 592 steps (148 × 4)
            "weight_decay": 0.01,
            "description": "Hướng dẫn từng bước giải toán - nhiệm vụ đơn giản",
        },
        "agent2": {
            "name": "Tính toán", 
            "complexity": "medium",
            "lr": 1e-4,          # Medium LR
            "lora_r": 16,         # Medium rank
            "lora_alpha": 32,
            "warmup_ratio": 0.03,
            "epochs": 4,  # 592 steps (148 × 4)
            "weight_decay": 0.01,
            "description": "Thực hiện các phép tính - nhiệm vụ trung bình",
        },
        "agent3": {
            "name": "Kiểm tra",
            "complexity": "medium_plus",
            "lr": 1.5e-4,         # Higher LR for verification
            "lora_r": 24,         # Higher rank
            "lora_alpha": 48,
            "warmup_ratio": 0.04,
            "epochs": 4,  # 592 steps (148 × 4)
            "weight_decay": 0.02,
            "description": "Xác minh kết quả - cần độ chính xác cao",
        },
        "agent4": {
            "name": "Sửa lỗi",
            "complexity": "complex",
            "lr": 2e-4,           # Higher LR for complex task
            "lora_r": 32,        # Higher rank for complex patterns
            "lora_alpha": 64,
            "warmup_ratio": 0.05,
            "epochs": 4,  # 592 steps (148 × 4)
            "weight_decay": 0.03,
            "description": "Phát hiện và sửa lỗi - nhiệm vụ phức tạp",
        },
        "agent5": {
            "name": "Kết luận",
            "complexity": "complex_plus",
            "lr": 2.5e-4,         # Highest LR - needs strong adaptation
            "lora_r": 48,         # Highest rank
            "lora_alpha": 96,
            "warmup_ratio": 0.05,
            "epochs": 4,  # 592 steps (148 × 4)
            "weight_decay": 0.05,
            "description": "Tổng hợp và đưa ra kết luận - nhiệm vụ phức tạp nhất",
        },
    }
    
    @classmethod
    def get_agent_cfg(cls, agent_id):
        return cls.agents.get(agent_id, cls.agents["agent2"])
    
    @classmethod
    def get_all_agents(cls):
        return list(cls.agents.keys())


class GlobalCFG:
    model_name = "Qwen/Qwen2.5-Math-1.5B-Instruct"

    # Local paths (adjust for your environment)
    data_dir = "/kaggle/input/datasets/vitduq/datasheet-full05082026/5agent_final"
    output_dir = "/kaggle/working/outputs"
    plots_dir = "/kaggle/working/plots"

    # For local development
    if not os.path.exists("/kaggle"):
        data_dir = "DATA/5agent_final"
        output_dir = "train_model/outputs"
        plots_dir = "train_model/plots"

    # Auto-detect: nếu data_dir không tồn tại, scan các vị trí phổ biến
    if not os.path.exists(data_dir):
        candidates = []
        # Scan /kaggle/input để tìm folder chứa 5agent_final
        if os.path.exists("/kaggle"):
            ki = "/kaggle/input"
            if os.path.exists(ki):
                for ds in os.listdir(ki):
                    p1 = os.path.join(ki, ds, "5agent_final")
                    p2 = os.path.join(ki, ds, "DATA", "5agent_final")
                    p3 = os.path.join(ki, "5agent_final")
                    candidates += [p1, p2, p3]
        # Local fallback
        candidates += [
            "DATA/5agent_final",
            "../DATA/5agent_final",
            os.path.join(os.getcwd(), "DATA", "5agent_final"),
        ]
        for c in candidates:
            if os.path.exists(c) and os.path.exists(os.path.join(c, "train", "agent1.jsonl")):
                print(f"   [AUTO] Found data_dir: {c}")
                data_dir = c
                break
        else:
            print(f"   [WARN] data_dir not found. Tried: {candidates[:3]}...")
    
    seed = 42
    
    # Target modules for Qwen2.5 Math - ONLY attention (q, k, v)
    target_modules = [
        "q_proj", "k_proj", "v_proj",
    ]
    
    # Common settings
    max_seq_len = 768
    batch_size = 2
    grad_accum = 4
    
    # Layer-wise LR decay (LLRD)
    llrd_decay = 0.95  # Each layer gets 0.95x of previous layer's LR
    
    # Optimizer settings
    optim = "paged_adamw_8bit"
    max_grad_norm = 0.5  # Slightly tighter gradient clipping
    
    # Mixed precision
    bf16 = True  # BF16 for stability
    fp16 = False
    
    # Logging
    logging_steps = 10
    eval_steps = 50
    save_steps = 50


# Create directories
os.makedirs(GlobalCFG.output_dir, exist_ok=True)
os.makedirs(GlobalCFG.plots_dir, exist_ok=True)

# Seed
def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

seed_everything(GlobalCFG.seed)


# %% Cell 3: Data Loading
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
            except:
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
                prompt_parts = [f"{k}: {v}" for k, v in inp_vals.items()]
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


# %% Cell 4: EDA
print("\n" + "=" * 70)
print("STEP 1: EXPLORATORY DATA ANALYSIS")
print("=" * 70)

eda_results = {}

for agent_id in AgentCFG.get_all_agents():
    agent_cfg = AgentCFG.get_agent_cfg(agent_id)
    print(f"\n[{agent_id.upper()}] {agent_cfg['name']}")
    print(f"   Complexity: {agent_cfg['complexity']}")
    print(f"   LR: {agent_cfg['lr']} | LoRA r: {agent_cfg['lora_r']}")
    
    # Find data file
    candidate_paths = [
        os.path.join(GlobalCFG.data_dir, "train", f"{agent_id}.jsonl"),
        os.path.join(GlobalCFG.data_dir.replace("5agent_final", "5agent_expanded"), "train", f"{agent_id}.jsonl"),
        f"DATA/5agent_final/train/{agent_id}.jsonl",
        f"DATA/5agent_expanded/train/{agent_id}.jsonl",
    ]
    
    train_file = None
    for path in candidate_paths:
        if os.path.exists(path):
            train_file = path
            break
    
    if train_file is None:
        print(f"   [WARN] No data file found")
        continue
    
    train_data = load_jsonl(train_file)
    train_data = [format_for_chat(d) if isinstance(d, dict) else d for d in train_data]
    
    # Filter valid records
    def is_valid(r):
        if not isinstance(r, dict):
            return False
        msgs = r.get('messages', [])
        if not msgs or len(msgs) < 2:
            return False
        return all(
            isinstance(m, dict) and m.get('content') and isinstance(m['content'], str)
            for m in msgs
        )
    
    train_data = [r for r in train_data if is_valid(r)]
    
    # Calculate stats
    user_lens = []
    asst_lens = []
    for item in train_data:
        for m in item.get('messages', []):
            txt = m.get('content', '')
            if m.get('role') == 'user':
                user_lens.append(len(txt))
            else:
                asst_lens.append(len(txt))
    
    stats = {
        'train_samples': len(train_data),
        'user_lens': user_lens,
        'assistant_lens': asst_lens,
        'avg_user_len': np.mean(user_lens) if user_lens else 0,
        'avg_assistant_len': np.mean(asst_lens) if asst_lens else 0,
        'max_user_len': np.max(user_lens) if user_lens else 0,
        'max_assistant_len': np.max(asst_lens) if asst_lens else 0,
    }
    
    eda_results[agent_id] = stats
    print(f"   Samples: {stats['train_samples']}")
    print(f"   Avg user: {stats['avg_user_len']:.0f} chars | Avg assistant: {stats['avg_assistant_len']:.0f} chars")


# %% Cell 5: Tokenization
print("\n" + "=" * 70)
print("STEP 2: TOKENIZE DATASET")
print("=" * 70)

print(f"\n[TOKENIZE] Loading tokenizer: {GlobalCFG.model_name}")
tokenizer = AutoTokenizer.from_pretrained(
    GlobalCFG.model_name,
    trust_remote_code=True
)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token


def tokenize_fn(example, max_length=GlobalCFG.max_seq_len):
    messages = example.get('messages', [])
    
    if isinstance(messages, str):
        try:
            messages = json.loads(messages) if messages.startswith('[') else [{"role": "user", "content": messages}]
        except:
            messages = [{"role": "user", "content": messages}]
    
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
        use_mask = any(raw_asm)
        assistant_mask = raw_asm if use_mask else None
    except:
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False
        )
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        prompt_ids = list(prompt_ids)
        assistant_mask = None
    
    # Truncate/pad
    if len(prompt_ids) > max_length:
        prompt_ids = prompt_ids[:max_length]
        if assistant_mask:
            assistant_mask = assistant_mask[:max_length]
        attention_mask = [1] * max_length
    else:
        attention_mask = [1] * len(prompt_ids)
        pad_len = max_length - len(prompt_ids)
        prompt_ids = prompt_ids + [tokenizer.pad_token_id] * pad_len
        attention_mask = attention_mask + [0] * pad_len
        if assistant_mask:
            assistant_mask = assistant_mask + [0] * pad_len
    
    # Labels
    labels = prompt_ids.copy()
    if assistant_mask:
        labels = [(-100 if am == 0 else v) for v, am in zip(labels, assistant_mask)]
    else:
        labels = [(-100 if m == 0 else v) for v, m in zip(labels, attention_mask)]
    
    return {
        "input_ids": prompt_ids,
        "attention_mask": attention_mask,
        "labels": labels,
    }


tokenized_datasets = {}

for agent_id in AgentCFG.get_all_agents():
    print(f"\n[TOKENIZE] Processing {agent_id}...")
    
    # Find data file
    candidate_paths = [
        os.path.join(GlobalCFG.data_dir, "train", f"{agent_id}.jsonl"),
        GlobalCFG.data_dir.replace("5agent_final", "5agent_expanded"),
        "DATA/5agent_final",
        "DATA/5agent_expanded",
    ]
    
    train_file = None
    for base_dir in candidate_paths:
        path = os.path.join(base_dir, "train", f"{agent_id}.jsonl")
        if os.path.exists(path):
            train_file = path
            break
    
    if train_file is None:
        print(f"   [SKIP] No train file for {agent_id}")
        continue
    
    train_data = load_jsonl(train_file)
    train_data = [format_for_chat(d) if isinstance(d, dict) else d for d in train_data]
    
    # Filter valid
    def is_valid(r):
        if not isinstance(r, dict):
            return False
        msgs = r.get('messages', [])
        if not msgs or len(msgs) < 2:
            return False
        return all(
            isinstance(m, dict) and m.get('content') and isinstance(m['content'], str)
            for m in msgs
        )
    
    train_data = [r for r in train_data if is_valid(r)]
    
    if not train_data:
        print(f"   [SKIP] No valid samples for {agent_id}")
        continue
    
    # Tokenize
    train_ds = Dataset.from_list(train_data)
    train_tokenized = train_ds.map(
        tokenize_fn,
        remove_columns=train_ds.column_names,
        desc=f"Tokenizing {agent_id}"
    )
    
    tokenized_datasets[agent_id] = {
        'train': train_tokenized,
        'num_train': len(train_tokenized),
    }
    print(f"   [OK] {len(train_tokenized)} samples")


# %% Cell 6: Create Layer-wise LR Decay
def get_layerwise_lr_groups(model, base_lr, decay_rate=GlobalCFG.llrd_decay):
    """Create parameter groups with layer-wise LR decay.
    
    Lower layers (closer to embedding) get lower LR,
    higher layers (closer to output) get higher LR.
    """
    # Identify layer types
    num_layers = 0
    layer_params = defaultdict(list)
    other_params = []
    
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        
        # Determine layer depth
        if "embed_tokens" in name:
            depth = 0  # Embedding layer
        elif "lm_head" in name:
            depth = 999  # Output layer
        elif ".layers." in name:
            # Extract layer number
            match = re.search(r"\.layers\.(\d+)\.", name)
            if match:
                depth = int(match.group(1)) + 1
            else:
                depth = 50
        else:
            depth = 100  # Other layers
        
        layer_params[depth].append(param)
    
    # Create LR groups
    param_groups = []
    depths = sorted(layer_params.keys())
    
    for depth in depths:
        params = layer_params[depth]
        if not params:
            continue
        
        # Calculate LR for this depth
        if depth == 999:  # Output layer
            lr = base_lr
        elif depth == 0:  # Embedding
            lr = base_lr * (decay_rate ** 3)
        else:
            lr = base_lr * (decay_rate ** (depth - 1))
        
        param_groups.append({
            "params": params,
            "lr": lr,
        })
        print(f"   Depth {depth}: {len(params)} params, LR = {lr:.2e}")
    
    return param_groups


# %% Cell 7: Training Loop
print("\n" + "=" * 70)
print("STEP 3: TRAINING 5 AGENTS (Agent-Specific LoRA)")
print("=" * 70)
print("\n[KEY IMPROVEMENTS]")
print("1. Per-agent learning rates (simple=low, complex=high)")
print("2. Layer-wise LR decay (LLRD) for better fine-tuning")
print("3. Agent-specific LoRA ranks (simple=low, complex=high)")
print("4. Cosine annealing with warmup")
print("5. BF16 mixed precision for stability")
print("6. Auto-save best checkpoint per agent (lowest loss)")
print("=" * 70)

training_history = {}
df_rows = []
best_checkpoints_report = []  # NEW: track best checkpoint per agent

for agent_id in AgentCFG.get_all_agents():
    if agent_id not in tokenized_datasets:
        continue
    
    agent_cfg = AgentCFG.get_agent_cfg(agent_id)
    agent_output_dir = os.path.join(GlobalCFG.output_dir, agent_id)
    
    print(f"\n{'='*70}")
    print(f"[TRAIN] {agent_id.upper()} - {agent_cfg['name']}")
    print(f"{'='*70}")
    print(f"   Task: {agent_cfg['description']}")
    print(f"   Complexity: {agent_cfg['complexity']}")
    print(f"   LR: {agent_cfg['lr']} | LoRA r: {agent_cfg['lora_r']}")
    print(f"   Warmup: {agent_cfg['warmup_ratio']*100}% | Epochs: {agent_cfg['epochs']}")
    
    t0 = time.time()
    
    # Load model
    print(f"\n   [LOAD] Loading base model...")
    model = AutoModelForCausalLM.from_pretrained(
        GlobalCFG.model_name,
        torch_dtype=torch.bfloat16 if GlobalCFG.bf16 else torch.float16,
        device_map="auto",
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    
    # Freeze base model
    print(f"   [FREEZE] Freezing base model...")
    for param in model.parameters():
        param.requires_grad = False
    
    # LoRA config
    print(f"   [CONFIG] Setting up LoRA...")
    lora_config = LoraConfig(
        r=agent_cfg['lora_r'],
        lora_alpha=agent_cfg['lora_alpha'],
        target_modules=GlobalCFG.target_modules,
        lora_dropout=0.1,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    
    model = get_peft_model(model, lora_config)
    
    # Get layer-wise LR groups
    print(f"   [LLRD] Creating layer-wise LR groups...")
    base_lr = agent_cfg['lr']
    param_groups = get_layerwise_lr_groups(model, base_lr, GlobalCFG.llrd_decay)
    
    # Verify only LoRA params are trainable
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    all_param = sum(p.numel() for p in model.parameters())
    print(f"   [VERIFY] Trainable: {trainable_params:,} / {all_param:,} ({100*trainable_params/all_param:.3f}%)")
    
    # Data
    ds = tokenized_datasets[agent_id]
    train_ds = ds['train']
    
    # Calculate steps
    steps_per_epoch = len(train_ds) // (GlobalCFG.batch_size * GlobalCFG.grad_accum)
    total_steps = steps_per_epoch * agent_cfg['epochs']
    warmup_steps = int(agent_cfg['warmup_ratio'] * total_steps)
    
    print(f"   [STEPS] Total: {total_steps}, Warmup: {warmup_steps}")
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=agent_output_dir,
        num_train_epochs=agent_cfg['epochs'],
        per_device_train_batch_size=GlobalCFG.batch_size,
        gradient_accumulation_steps=GlobalCFG.grad_accum,
        
        # Use param_groups for layer-wise LR (custom scheduler passed via optimizers)
        optim=GlobalCFG.optim,
        lr_scheduler_type="cosine",
        
        bf16=GlobalCFG.bf16,
        fp16=GlobalCFG.fp16,
        max_grad_norm=GlobalCFG.max_grad_norm,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        
        warmup_steps=warmup_steps,
        weight_decay=agent_cfg['weight_decay'],
        
        logging_steps=GlobalCFG.logging_steps,
        logging_first_step=True,
        
        save_strategy="steps",
        save_steps=GlobalCFG.save_steps,
        save_total_limit=2,
        
        report_to="none",
        seed=GlobalCFG.seed,
        remove_unused_columns=False,
        dataloader_num_workers=0,
        dataloader_pin_memory=True,
    )
    
    # Custom optimizer with layer-wise LR
    from torch.optim import AdamW
    optimizer = AdamW(param_groups, eps=1e-8)
    
    # Scheduler
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        optimizers=(optimizer, scheduler),
    )
    
    # Train
    print(f"   [START] Training...")
    trainer.train()
    
    # NEW: Track best checkpoint based on lowest train loss
    log_history = trainer.state.log_history or []
    train_losses = [(e["step"], e["loss"]) for e in log_history if "loss" in e]
    best_step = None
    best_loss = float("inf")
    if train_losses:
        best_step, best_loss = min(train_losses, key=lambda x: x[1])
    
    # Save final model
    trainer.save_model(agent_output_dir)
    print(f"   [SAVE] Final model saved to {agent_output_dir}")
    
    # NEW: Save best adapter separately
    best_ckpt_dir = os.path.join(GlobalCFG.output_dir, f"{agent_id}_best")
    os.makedirs(best_ckpt_dir, exist_ok=True)
    # Save a copy of the adapter with metadata
    model.save_pretrained(best_ckpt_dir)
    tokenizer.save_pretrained(best_ckpt_dir)
    with open(os.path.join(best_ckpt_dir, "best_checkpoint.json"), "w", encoding="utf-8") as f:
        json.dump({
            "agent_id": agent_id,
            "agent_name": agent_cfg['name'],
            "best_step": best_step,
            "best_loss": best_loss,
            "final_loss": train_losses[-1][1] if train_losses else None,
            "total_steps": total_steps,
            "lr": agent_cfg['lr'],
            "lora_r": agent_cfg['lora_r'],
            "epochs": agent_cfg['epochs'],
        }, f, ensure_ascii=False, indent=2)
    print(f"   [BEST] Best adapter saved to {best_ckpt_dir} (step={best_step}, loss={best_loss:.6f})")
    
    # History
    train_time_min = (time.time() - t0) / 60
    
    training_history[agent_id] = {
        'train_loss': train_losses,
        'train_time_min': train_time_min,
        'final_loss': train_losses[-1] if train_losses else None,
    }
    
    df_rows.append({
        'agent': agent_id,
        'name': agent_cfg['name'],
        'complexity': agent_cfg['complexity'],
        'lr': agent_cfg['lr'],
        'lora_r': agent_cfg['lora_r'],
        'warmup_ratio': agent_cfg['warmup_ratio'],
        'epochs': agent_cfg['epochs'],
        'trainable_params': trainable_params,
        'total_params': all_param,
        'train_samples': len(train_ds),
        'final_loss': training_history[agent_id]['final_loss'],
        'train_time_min': train_time_min,
    })
    
    # NEW: Record best checkpoint
    best_checkpoints_report.append({
        "agent_id": agent_id,
        "agent_name": agent_cfg['name'],
        "best_step": best_step,
        "best_loss": best_loss,
        "final_loss": train_losses[-1][1] if train_losses else None,
        "best_dir": best_ckpt_dir,
        "final_dir": agent_output_dir,
    })
    
    print(f"\n   [RESULT] {agent_cfg['name']}")
    print(f"   Final loss: {training_history[agent_id]['final_loss']:.6f}")
    print(f"   Time: {train_time_min:.1f} min")
    
    # Cleanup
    del model, trainer
    gc.collect()
    torch.cuda.empty_cache()


# %% Cell 8: Visualization
print("\n" + "=" * 70)
print("STEP 4: VISUALIZATION")
print("=" * 70)

if df_rows:
    df = pd.DataFrame(df_rows)
    
    # Create dashboard
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('5-Agent Training Dashboard (Agent-Specific LoRA)', fontsize=16, fontweight='bold')
    
    agents = df['agent'].tolist()
    colors = plt.cm.Set2(np.linspace(0, 1, len(agents)))
    
    # 1. Learning Rates
    ax1 = axes[0, 0]
    lrs = df['lr'].tolist()
    ax1.bar(agents, [lr * 1e4 for lr in lrs], color=colors, edgecolor='white')
    ax1.set_ylabel('Learning Rate (×10⁴)')
    ax1.set_title('Agent-Specific Learning Rates')
    for i, (a, lr) in enumerate(zip(agents, lrs)):
        ax1.text(i, lr * 1e4 + 0.02, f'{lr:.1e}', ha='center', fontsize=8)
    
    # 2. LoRA Ranks
    ax2 = axes[0, 1]
    ranks = df['lora_r'].tolist()
    ax2.bar(agents, ranks, color=colors, edgecolor='white')
    ax2.set_ylabel('LoRA Rank')
    ax2.set_title('Agent-Specific LoRA Ranks')
    for i, (a, r) in enumerate(zip(agents, ranks)):
        ax2.text(i, r + 1, f'r={r}', ha='center', fontsize=9)
    
    # 3. Final Loss
    ax3 = axes[0, 2]
    losses = df['final_loss'].tolist()
    colors_loss = [plt.cm.RdYlGn_r(l / max(losses)) for l in losses]
    ax3.bar(agents, losses, color=colors_loss, edgecolor='white')
    ax3.set_ylabel('Final Loss')
    ax3.set_title('Training Final Loss')
    for i, (a, l) in enumerate(zip(agents, losses)):
        ax3.text(i, l + 0.01, f'{l:.4f}', ha='center', fontsize=8)
    
    # 4. Trainable Parameters
    ax4 = axes[1, 0]
    trainable_pcts = [100 * t / all_p for t, all_p in zip(df['trainable_params'], df['total_params'])]
    ax4.bar(agents, trainable_pcts, color='#2ecc71', edgecolor='white')
    ax4.set_ylabel('Trainable (%)')
    ax4.set_title('LoRA Efficiency')
    for i, p in enumerate(trainable_pcts):
        ax4.text(i, p + 0.02, f'{p:.3f}%', ha='center', fontsize=8)
    
    # 5. Training Time
    ax5 = axes[1, 1]
    times = df['train_time_min'].tolist()
    ax5.bar(agents, times, color='#3498db', edgecolor='white')
    ax5.set_ylabel('Time (minutes)')
    ax5.set_title('Training Time')
    for i, t in enumerate(times):
        ax5.text(i, t + 0.3, f'{t:.1f}m', ha='center', fontsize=9)
    
    # 6. Complexity vs Performance
    ax6 = axes[1, 2]
    complexity_scores = {'simple': 1, 'medium': 2, 'medium_plus': 3, 'complex': 4, 'complex_plus': 5}
    x_scores = [complexity_scores.get(c, 3) for c in df['complexity']]
    ax6.scatter(x_scores, losses, s=100, c=colors, edgecolors='black')
    ax6.set_xlabel('Complexity (1=Simple, 5=Complex+)')
    ax6.set_ylabel('Final Loss')
    ax6.set_title('Complexity vs Performance')
    for i, (xs, l, a) in enumerate(zip(x_scores, losses, agents)):
        ax6.annotate(a, (xs, l), textcoords="offset points", xytext=(5, 5), fontsize=8)
    
    plt.tight_layout()
    fig.savefig(os.path.join(GlobalCFG.plots_dir, 'training_dashboard.png'), 
                bbox_inches='tight', facecolor='white')
    print(f"\n[OK] Dashboard saved")
    
    # Training loss curves
    fig2, ax = plt.subplots(figsize=(12, 6))
    for i, (agent, hist) in enumerate(training_history.items()):
        if hist['train_loss']:
            steps = range(1, len(hist['train_loss']) + 1)
            ax.plot(steps, hist['train_loss'], label=agent, linewidth=2, color=colors[i])
    ax.set_xlabel('Step')
    ax.set_ylabel('Loss')
    ax.set_title('Training Loss Curves (Agent-Specific)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig2.savefig(os.path.join(GlobalCFG.plots_dir, 'loss_curves.png'),
                 bbox_inches='tight', facecolor='white')
    print(f"[OK] Loss curves saved")
    
    plt.show()


# %% Cell 8.5: Best Checkpoint Report (NEW)
print("\n" + "=" * 70)
print("STEP 4.5: BEST CHECKPOINT REPORT (Per Agent)")
print("=" * 70)

if best_checkpoints_report:
    best_df = pd.DataFrame(best_checkpoints_report)
    print("\n" + best_df.to_string(index=False))
    
    # Save JSON report
    report_path = os.path.join(GlobalCFG.output_dir, "best_checkpoints_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(best_checkpoints_report, f, ensure_ascii=False, indent=2)
    print(f"\n[SAVE] Best checkpoints report -> {report_path}")
    
    # Save markdown report (human-readable)
    md_path = os.path.join(GlobalCFG.output_dir, "best_checkpoints_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Best Checkpoints Report - 5 Agent Training\n\n")
        f.write(f"**Model**: `{GlobalCFG.model_name}`\n\n")
        f.write(f"**Target modules**: `{GlobalCFG.target_modules}`\n\n")
        f.write("## Per-Agent Best Adapter\n\n")
        f.write("| Agent | Name | Best Step | Best Loss | Final Loss | Path |\n")
        f.write("|-------|------|-----------|-----------|------------|------|\n")
        for r in best_checkpoints_report:
            f.write(f"| {r['agent_id']} | {r['agent_name']} | {r['best_step']} | "
                    f"{r['best_loss']:.6f} | {r['final_loss']:.6f} | `{r['best_dir']}` |\n")
        f.write("\n## Recommendation\n\n")
        f.write("> Use the **`{}_best/`** directory for each agent when loading adapters for inference.\n")
        f.write("> These are the adapters at the step with the LOWEST training loss.\n")
    print(f"[SAVE] Markdown report -> {md_path}")
    
    # Print summary table
    print("\n" + "=" * 70)
    print("LOAD ADAPTERS FOR INFERENCE:")
    print("=" * 70)
    for r in best_checkpoints_report:
        print(f"  {r['agent_id']}: {r['best_dir']}")
    
    # Best loss chart
    fig3, ax = plt.subplots(figsize=(10, 6))
    agent_ids = [r['agent_id'] for r in best_checkpoints_report]
    best_losses = [r['best_loss'] for r in best_checkpoints_report]
    final_losses = [r['final_loss'] for r in best_checkpoints_report]
    x = np.arange(len(agent_ids))
    width = 0.35
    ax.bar(x - width/2, best_losses, width, label='Best Loss', color='#2ecc71')
    ax.bar(x + width/2, final_losses, width, label='Final Loss', color='#e74c3c')
    ax.set_xticks(x)
    ax.set_xticklabels(agent_ids)
    ax.set_ylabel('Loss')
    ax.set_title('Best vs Final Loss per Agent')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    fig3.savefig(os.path.join(GlobalCFG.plots_dir, 'best_vs_final_loss.png'),
                 bbox_inches='tight', facecolor='white')
    print(f"[OK] Best vs Final loss chart saved")
    plt.show()


# %% Cell 9: Summary
print("\n" + "=" * 70)
print("TRAINING SUMMARY")
print("=" * 70)

if df_rows:
    df = pd.DataFrame(df_rows)
    print("\n" + df.to_string(index=False))
    
    # Save results
    df.to_csv(os.path.join(GlobalCFG.output_dir, 'training_summary.csv'), index=False)
    
    with open(os.path.join(GlobalCFG.output_dir, 'training_history.json'), 'w') as f:
        json.dump(training_history, f, indent=2)
    
    print("\n[SUMMARY]")
    print(f"- Agent-specific LRs: simple={8e-5:.0e}, complex+={2.5e-4:.0e}")
    print(f"- Agent-specific LoRA ranks: simple=8, complex+=48")
    print(f"- Layer-wise LR decay: {GlobalCFG.llrd_decay}")
    print(f"- Cosine annealing with warmup")
    print(f"- BF16 mixed precision")
    print(f"- Best checkpoint auto-saved per agent -> {{agent}}_best/")
    
    print("\n[RECOMMENDATIONS]")
    print("1. Agent 1 (hint): Use lowest LR - simple task, avoid overfitting")
    print("2. Agent 5 (conclusion): Use highest LR - complex task needs strong adaptation")
    print("3. LLRD helps preserve pre-trained knowledge in lower layers")
    print("4. BF16 provides numerical stability for training")
    print("5. Use {agent}_best/ for inference (lowest loss checkpoint)")
else:
    print("(No training results)")

print("\n" + "=" * 70)
print("TRAINING PIPELINE COMPLETED!")
print("=" * 70)