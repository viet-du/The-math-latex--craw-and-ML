"""
5-Agent Math Solver - Training Pipeline
Qwen2.5-Math-1.5B-Instruct with LoRA Only (No Full Fine-Tuning)
================================================================
Changes from original:
- Lower learning rate (1e-4 instead of 2e-4)
- Strictly LoRA-only training (base model frozen)
- Gradient checkpointing enabled
- More conservative training settings
"""

# %% Cell 1: Imports & Setup
import os, sys, re, json, time, gc, random
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
from pathlib import Path
from datasets import Dataset, load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model, TaskType, inject_adapter_in_model

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
    data_dir   = "/kaggle/input/datasets/vitduq/datasheet-full05082026/5agent_final"
    output_dir = "/kaggle/working/outputs"
    plots_dir  = "/kaggle/working/plots"
    seed       = 42

    # Target modules for Qwen2.5
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

    # ============================================================
    # TRAINING HYPERPARAMETERS - CONSERVATIVE SETTINGS FOR LoRA
    # ============================================================
    fp16         = False
    bf16         = False
    optim        = "paged_adamw_8bit"
    max_seq_len  = 768
    epochs       = 3
    batch_size   = 2
    grad_accum   = 4

    # IMPORTANT: Lower learning rate for LoRA-only training
    # Original: 2e-4 (too high for LoRA, causes instability)
    # New: 1e-4 (more stable for LoRA adapters)
    lr           = 1e-4

    # Conservative weight decay for LoRA
    weight_decay = 0.01

    # Warmup - slower warmup for stability
    warmup_ratio = 0.1  # 10% warmup (was 5%)

    # Gradient clipping for stability
    max_grad_norm = 1.0

    active_agents = ["agent1", "agent2", "agent3", "agent4", "agent5"]

    # Per-agent LoRA rank - keeping consistent ranks
    lora_r = {
        "agent1": 16,
        "agent2": 32,
        "agent3": 16,
        "agent4": 16,
        "agent5": 16,
    }

    # LoRA-specific hyperparameters
    lora_alpha = 32  # Scale factor (higher = stronger adaptation)
    lora_dropout = 0.1  # Slightly higher dropout for regularization

# Create output directories
os.makedirs(CFG.output_dir, exist_ok=True)
os.makedirs(CFG.plots_dir, exist_ok=True)

# Seed
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
    """Normalize record into dict {messages: [user, assistant]}.
    Handles data with user-content as JSON string {'input_values': {...}, 'output': '...'}
    Returns a dict with same keys but normalized 'messages'.
    """
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

# %% Cell 4: EDA & Visualization (Matplotlib)
print("\n" + "=" * 70)
print("STEP 1: EXPLORATORY DATA ANALYSIS (EDA)")
print("=" * 70)

eda_results = {}

for agent_id in CFG.active_agents:
    print(f"\n[EDA] {agent_id.upper()}")

    candidate_dirs = [
        CFG.data_dir,
        CFG.data_dir.replace("5agent_expanded", "5agent_final"),
        "/kaggle/input/5agent_final",
        "/kaggle/input/5agent_expanded",
        "/kaggle/input/datasets/vitduq/5agent_final",
        "/kaggle/input/datasets/vitduq/5agent_expanded",
    ]
    actual_data_dir = None
    for cand in candidate_dirs:
        if cand and os.path.exists(os.path.join(cand, "train", f"{agent_id}.jsonl")):
            actual_data_dir = cand
            break

    if actual_data_dir is None:
        print(f"   [WARN] No data file found for {agent_id}")
        continue

    train_file = os.path.join(actual_data_dir, "train", f"{agent_id}.jsonl")
    test_file  = os.path.join(actual_data_dir, "test",  f"{agent_id}.jsonl")

    train_data = load_jsonl(train_file)
    test_data = load_jsonl(test_file) if os.path.exists(test_file) else []

    train_msgs = sum(len(d.get('messages', [])) for d in train_data)
    test_msgs = sum(len(d.get('messages', [])) for d in test_data)

    user_lens = []
    asst_lens = []

    for item in train_data + test_data:
        msgs = item.get('messages', [])
        for m in msgs:
            txt = m.get('content', '')
            if m.get('role') == 'user':
                user_lens.append(len(txt))
            else:
                asst_lens.append(len(txt))

    stats = {
        'train_samples': len(train_data),
        'test_samples': len(test_data),
        'train_messages': train_msgs,
        'test_messages': test_msgs,
        'user_lens': user_lens,
        'assistant_lens': asst_lens,
        'avg_user_len': np.mean(user_lens) if user_lens else 0,
        'avg_assistant_len': np.mean(asst_lens) if asst_lens else 0,
        'max_user_len': np.max(user_lens) if user_lens else 0,
        'max_assistant_len': np.max(asst_lens) if asst_lens else 0,
    }

    eda_results[agent_id] = stats
    print(f"   Train: {stats['train_samples']} samples")
    print(f"   Test: {stats['test_samples']} samples")
    print(f"   Avg user len: {stats['avg_user_len']:.0f} chars")
    print(f"   Avg assistant len: {stats['avg_assistant_len']:.0f} chars")

# Create EDA Matplotlib Charts
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('EDA - Exploratory Data Analysis', fontsize=16, fontweight='bold')

agents = list(eda_results.keys())

# Plot 1: Samples per agent (bar)
ax1 = axes[0, 0]
x = np.arange(len(agents))
w = 0.35
train_counts = [eda_results[a]['train_samples'] for a in agents]
test_counts = [eda_results[a]['test_samples'] for a in agents]
bars1 = ax1.bar(x - w/2, train_counts, w, label='Train', color='#2ecc71', edgecolor='white')
bars2 = ax1.bar(x + w/2, test_counts, w, label='Test', color='#e74c3c', edgecolor='white')
ax1.set_xticks(x)
ax1.set_xticklabels(agents)
ax1.set_ylabel('Count')
ax1.set_title('Samples per Agent')
ax1.legend()
for bar in bars1 + bars2:
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f'{int(bar.get_height())}',
             ha='center', va='bottom', fontsize=8)

# Plot 2: Average message length
ax2 = axes[0, 1]
user_lens = [eda_results[a]['avg_user_len'] for a in agents]
asst_lens = [eda_results[a]['avg_assistant_len'] for a in agents]
bars3 = ax2.bar(x - w/2, user_lens, w, label='User', color='#3498db', edgecolor='white')
bars4 = ax2.bar(x + w/2, asst_lens, w, label='Assistant', color='#9b59b6', edgecolor='white')
ax2.set_xticks(x)
ax2.set_xticklabels(agents)
ax2.set_ylabel('Characters')
ax2.set_title('Average Message Length')
ax2.legend()

# Plot 3: Distribution of user length (histogram)
ax3 = axes[1, 0]
colors = plt.cm.Set2(np.linspace(0, 1, len(agents)))
for i, agent in enumerate(agents):
    lens = eda_results[agent]['user_lens']
    if lens:
        ax3.hist(lens, bins=30, alpha=0.5, label=agent, color=colors[i])
ax3.set_xlabel('Length (chars)')
ax3.set_ylabel('Frequency')
ax3.set_title('Distribution of User Input Length')
ax3.legend()

# Plot 4: Distribution of assistant length (histogram)
ax4 = axes[1, 1]
for i, agent in enumerate(agents):
    lens = eda_results[agent]['assistant_lens']
    if lens:
        ax4.hist(lens, bins=30, alpha=0.5, label=agent, color=colors[i])
ax4.set_xlabel('Length (chars)')
ax4.set_ylabel('Frequency')
ax4.set_title('Distribution of Assistant Output Length')
ax4.legend()

plt.tight_layout()
eda_fig_path = os.path.join(CFG.plots_dir, '01_eda_overview.png')
fig.savefig(eda_fig_path, bbox_inches='tight', facecolor='white')
print(f"\n[OK] EDA chart saved: {eda_fig_path}")
plt.show()

# %% Cell 5: Feature Analysis
print("\n" + "=" * 70)
print("STEP 2: FEATURE ANALYSIS")
print("=" * 70)

feature_results = {}

for agent_id in CFG.active_agents:
    print(f"\n[FEATURE] {agent_id.upper()}")

    train_file = os.path.join(CFG.data_dir, "train", f"{agent_id}.jsonl")
    if not os.path.exists(train_file):
        print(f"   [WARN] File not found: {train_file}")
        continue

    train_data = load_jsonl(train_file)
    print(f"   Loaded {len(train_data)} samples")

    input_lens = []
    output_lens = []
    total_lens = []

    for item in train_data:
        msgs = item.get('messages', [])
        inp = sum(len(m.get('content', '')) for m in msgs if m.get('role') == 'user')
        out = sum(len(m.get('content', '')) for m in msgs if m.get('role') == 'assistant')
        input_lens.append(inp)
        output_lens.append(out)
        total_lens.append(inp + out)

    if not total_lens:
        print(f"   [WARN] No messages data for {agent_id}")
        continue

    stats = {
        'input_lens': input_lens,
        'output_lens': output_lens,
        'total_tokens': total_lens,
        'avg_input': np.mean(input_lens) if input_lens else 0,
        'avg_output': np.mean(output_lens) if output_lens else 0,
        'avg_total': np.mean(total_lens) if total_lens else 0,
        'max_total': np.max(total_lens) if total_lens else 0,
        'p95_total': np.percentile(total_lens, 95) if total_lens else 0,
        'p99_total': np.percentile(total_lens, 99) if total_lens else 0,
    }

    feature_results[agent_id] = stats
    print(f"   Avg input: {stats['avg_input']:.0f} | Avg output: {stats['avg_output']:.0f}")
    print(f"   Max: {stats['max_total']:.0f} | P95: {stats['p95_total']:.0f}")

# Feature Analysis Matplotlib Charts
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Feature Analysis', fontsize=16, fontweight='bold')

agents = [a for a in CFG.active_agents if a in feature_results and len(feature_results[a]['total_tokens']) > 0]

if len(agents) == 0:
    print("No data available for visualization")
else:
    # Plot 1: Token distribution by agent (box)
    ax1 = axes[0, 0]
    data_box = [feature_results[a]['total_tokens'] for a in agents]
    bp = ax1.boxplot(data_box, tick_labels=agents, patch_artist=True)
    colors_box = plt.cm.Set2(np.linspace(0, 1, len(agents)))
    for patch, color in zip(bp['boxes'], colors_box):
        patch.set_facecolor(color)
    ax1.set_ylabel('Total Length (chars)')
    ax1.set_title('Token Distribution by Agent')

    # Plot 2: Average token counts
    ax2 = axes[0, 1]
    avg_inputs = [feature_results[a]['avg_input'] for a in agents]
    avg_outputs = [feature_results[a]['avg_output'] for a in agents]
    avg_totals = [feature_results[a]['avg_total'] for a in agents]
    x = np.arange(len(agents))
    w = 0.25
    ax2.bar(x - w, avg_inputs, w, label='Input', color='#3498db', edgecolor='white')
    ax2.bar(x, avg_outputs, w, label='Output', color='#e74c3c', edgecolor='white')
    ax2.bar(x + w, avg_totals, w, label='Total', color='#2ecc71', edgecolor='white')
    ax2.set_xticks(x)
    ax2.set_xticklabels(agents)
    ax2.set_ylabel('Length (chars)')
    ax2.set_title('Average Token Counts')
    ax2.legend()

    # Plot 3: Total length histogram
    ax3 = axes[1, 0]
    all_lens = []
    for a in agents:
        all_lens.extend(feature_results[a]['total_tokens'])
    ax3.hist(all_lens, bins=50, color='#3498db', alpha=0.7, edgecolor='white')
    ax3.set_xlabel('Total Length (chars)')
    ax3.set_ylabel('Frequency')
    ax3.set_title('Overall Total Length Distribution')
    ax3.axvline(np.mean(all_lens), color='red', linestyle='--', label=f'Mean: {np.mean(all_lens):.0f}')
    ax3.legend()

    # Plot 4: Max/P95/P99 stats
    ax4 = axes[1, 1]
    max_vals = [feature_results[a]['max_total'] for a in agents]
    p95_vals = [feature_results[a]['p95_total'] for a in agents]
    p99_vals = [feature_results[a]['p99_total'] for a in agents]
    x = np.arange(len(agents))
    w = 0.25
    ax4.bar(x - w, max_vals, w, label='Max', color='#c0392b', edgecolor='white')
    ax4.bar(x, p95_vals, w, label='P95', color='#f39c12', edgecolor='white')
    ax4.bar(x + w, p99_vals, w, label='P99', color='#27ae60', edgecolor='white')
    ax4.set_xticks(x)
    ax4.set_xticklabels(agents)
    ax4.set_ylabel('Length (chars)')
    ax4.set_title('Max / P95 / P99 Stats')
    ax4.legend()

    plt.tight_layout()
    feat_fig_path = os.path.join(CFG.plots_dir, '02_feature_analysis.png')
    fig.savefig(feat_fig_path, bbox_inches='tight', facecolor='white')
    print(f"\n[OK] Feature analysis saved: {feat_fig_path}")
    plt.show()

# %% Cell 6: Tokenize Dataset
print("\n" + "=" * 70)
print("STEP 3: TOKENIZE DATASET")
print("=" * 70)

print(f"\n[TOKENIZE] Loading tokenizer: {CFG.model_name}")
tokenizer = AutoTokenizer.from_pretrained(
    CFG.model_name,
    trust_remote_code=True
)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

def tokenize_fn(example, max_length=CFG.max_seq_len):
    messages = example.get('messages', [])

    if isinstance(messages, str):
        try:
            messages = json.loads(messages) if messages.startswith('[') else [{"role": "user", "content": messages}]
        except Exception:
            messages = [{"role": "user", "content": messages}]

    use_assistant_mask = False
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
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        prompt_ids = list(prompt_ids)
        assistant_mask = None

    # Pad / truncate to max_length
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

    # Labels = input_ids copy, then mask (a) pad positions and (b) system+user positions
    result = {
        "input_ids": prompt_ids,
        "attention_mask": attention_mask,
    }
    result["labels"] = result["input_ids"].copy()
    result["labels"] = [(-100 if m == 0 else v) for v, m in zip(result["labels"], result["attention_mask"])]
    if use_assistant_mask and assistant_mask is not None:
        result["labels"] = [
            (-100 if m == 0 else v) for v, m in zip(result["labels"], assistant_mask)
        ]

    return result

tokenized_datasets = {}

for agent_id in CFG.active_agents:
    print(f"\n[TOKENIZE] Processing {agent_id}...")

    candidate_dirs = [
        CFG.data_dir,
        CFG.data_dir.replace("5agent_expanded", "5agent_final"),
        "/kaggle/input/5agent_final",
        "/kaggle/input/5agent_expanded",
        "/kaggle/input/datasets/vitduq/5agent_final",
        "/kaggle/input/datasets/vitduq/5agent_expanded",
    ]
    actual_data_dir = None
    for cand in candidate_dirs:
        if cand and os.path.exists(os.path.join(cand, "train", f"{agent_id}.jsonl")):
            actual_data_dir = cand
            break

    if actual_data_dir is None:
        print(f"[WARN] Skipping {agent_id} (no train file)")
        continue

    train_file = os.path.join(actual_data_dir, "train", f"{agent_id}.jsonl")
    test_file  = os.path.join(actual_data_dir, "test",  f"{agent_id}.jsonl")

    train_data = load_jsonl(train_file)
    test_data  = load_jsonl(test_file) if os.path.exists(test_file) else []

    if train_data and isinstance(train_data[0], dict):
        first_keys = list(train_data[0].keys())
        first_msgs = train_data[0].get('messages', [])
        role_set = sorted({m.get('role', '?') for m in first_msgs if isinstance(m, dict)})
        print(f"   [DEBUG] first record keys={first_keys}, roles={role_set}")

    print(f"   Train: {len(train_data)}, Test: {len(test_data)}")

    # Normalize via format_for_chat
    train_data = [format_for_chat(d) if isinstance(d, dict) else d for d in train_data]
    test_data = [format_for_chat(d) if isinstance(d, dict) else d for d in test_data]

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

    invalid_reasons = {"not_dict": 0, "no_messages": 0, "bad_msg": 0, "empty_content": 0}

    def is_valid_with_reason(record):
        if not isinstance(record, dict):
            invalid_reasons["not_dict"] += 1
            return False
        msgs = record.get('messages')
        if not msgs or not isinstance(msgs, list) or len(msgs) < 2:
            invalid_reasons["no_messages"] += 1
            return False
        bad = False
        empty = False
        for m in msgs:
            if not isinstance(m, dict):
                bad = True
                break
            c = m.get('content')
            if not c or not isinstance(c, str):
                empty = True
                break
        if bad:
            invalid_reasons["bad_msg"] += 1
            return False
        if empty:
            invalid_reasons["empty_content"] += 1
            return False
        return True

    train_data = [r for r in train_data if is_valid_with_reason(r)]
    test_data  = [r for r in test_data  if is_valid_with_reason(r)]
    print(f"   After filter: Train: {len(train_data)}, Test: {len(test_data)}")
    if any(invalid_reasons.values()):
        print(f"   [DEBUG] invalid reasons: {invalid_reasons}")

    if not train_data:
        print(f"   [WARN] No valid samples for {agent_id}, skipping")
        continue

    # Convert to datasets
    train_ds = Dataset.from_list(train_data)
    test_ds = Dataset.from_list(test_data) if test_data else None

    train_tokenized = train_ds.map(
        tokenize_fn,
        remove_columns=train_ds.column_names,
        desc=f"Tokenizing {agent_id} train"
    )

    test_tokenized = None
    if test_ds:
        test_tokenized = test_ds.map(
            tokenize_fn,
            remove_columns=test_ds.column_names,
            desc=f"Tokenizing {agent_id} test"
        )

    if test_tokenized is None or len(test_tokenized) == 0:
        n_test = 0 if test_tokenized is None else len(test_tokenized)
        print(
            f"   [WARN] {agent_id}: test split empty ({n_test} rows), "
            f"falling back to train split for evaluation."
        )
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

# %% Cell 7: Training Loop - LoRA ONLY (Base Model Frozen)
print("\n" + "=" * 70)
print("STEP 4: TRAINING 5 AGENTS (LoRA ONLY - BASE MODEL FROZEN)")
print("=" * 70)
print("[INFO] Key changes from full fine-tuning:")
print("       - Learning rate: 1e-4 (was 2e-4)")
print("       - Only LoRA adapter weights are trainable")
print("       - Base model parameters are completely frozen")
print("       - Gradient checkpointing enabled for memory efficiency")
print("       - Higher dropout (0.1) for regularization")
print("=" * 70)

training_history = {}
df_rows = []

for agent_id in CFG.active_agents:
    if agent_id not in tokenized_datasets:
        continue

    lora_rank = CFG.lora_r.get(agent_id, 16)
    agent_output_dir = os.path.join(CFG.output_dir, agent_id)

    print(f"\n{'='*70}")
    print(f"[TRAIN] {agent_id.upper()} (LoRA r={lora_rank}, lr={CFG.lr})")
    print(f"{'='*70}")

    t0 = time.time()

    # ============================================================
    # LOAD BASE MODEL - FROZEN (NO FULL FINE-TUNING)
    # ============================================================
    print(f"   [LOAD] Loading base model...")
    model = AutoModelForCausalLM.from_pretrained(
        CFG.model_name,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )

    # ============================================================
    # FREEZE ALL BASE MODEL PARAMETERS - CRITICAL FOR LoRA ONLY
    # ============================================================
    print(f"   [FREEZE] Freezing base model parameters...")
    for name, param in model.named_parameters():
        param.requires_grad = False

    # Count frozen parameters
    frozen_params = sum(p.numel() for p in model.parameters() if not p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"   [INFO] Frozen params: {frozen_params:,} / {total_params:,} ({100*frozen_params/total_params:.1f}%)")

    # ============================================================
    # LoRA CONFIGURATION - STRICT LoRA ONLY
    # ============================================================
    print(f"   [CONFIG] Setting up LoRA adapter...")
    lora_config = LoraConfig(
        r=lora_rank,                          # LoRA rank
        lora_alpha=CFG.lora_alpha,            # Scaling factor (higher = stronger adaptation)
        target_modules=CFG.target_modules,   # Qwen attention layers
        lora_dropout=CFG.lora_dropout,        # Dropout for regularization
        bias="none",                          # Don't train biases
        task_type=TaskType.CAUSAL_LM,
    )

    # Apply LoRA to model
    model = get_peft_model(model, lora_config)

    # Verify ONLY LoRA parameters are trainable
    trainable_params, all_param = model.get_trainable_weights()
    print(f"   [VERIFY] Trainable params: {trainable_params:,} / {all_param:,} ({100*trainable_params/all_param:.3f}%)")

    # Double-check: ensure base model is NOT trainable
    for name, param in model.named_parameters():
        if "lora" not in name.lower() and param.requires_grad:
            print(f"   [ERROR] Non-LoRA parameter is trainable: {name}")
            raise ValueError(f"Base model parameter {name} is trainable!")

    model.print_trainable_parameters()

    # Data
    ds = tokenized_datasets[agent_id]
    train_ds = ds['train']
    eval_ds = ds['test']
    do_eval = ds.get('do_eval', len(eval_ds) > 0 if eval_ds is not None else False)

    # ============================================================
    # TRAINING ARGUMENTS - OPTIMIZED FOR LoRA
    # ============================================================
    print(f"   [CONFIG] Setting up training arguments...")

    # Calculate total steps for warmup
    steps_per_epoch = len(train_ds) // (CFG.batch_size * CFG.grad_accum)
    total_steps = steps_per_epoch * CFG.epochs
    warmup_steps = int(CFG.warmup_ratio * total_steps)

    training_args = TrainingArguments(
        output_dir=agent_output_dir,
        num_train_epochs=CFG.epochs,
        per_device_train_batch_size=CFG.batch_size,
        gradient_accumulation_steps=CFG.grad_accum,
        learning_rate=CFG.lr,                    # Lower LR for LoRA
        warmup_steps=warmup_steps,               # Slower warmup
        weight_decay=CFG.weight_decay,
        optim=CFG.optim,
        fp16=CFG.fp16,
        bf16=CFG.bf16,

        # Logging
        logging_steps=10,
        logging_first_step=True,

        # Saving
        save_strategy="steps" if do_eval else "no",
        save_steps=50 if do_eval else 0,        # Save less frequently
        save_total_limit=2,                     # Keep only 2 checkpoints

        # Evaluation
        eval_strategy="steps" if do_eval else "no",
        eval_steps=50 if do_eval else 0,
        load_best_model_at_end=True if do_eval else False,
        metric_for_best_model="eval_loss" if do_eval else None,
        greater_is_better=False,

        # ============================================================
        # GRADIENT SETTINGS FOR STABILITY
        # ============================================================
        max_grad_norm=CFG.max_grad_norm,        # Gradient clipping
        gradient_checkpointing=True,            # Enable for memory efficiency
        gradient_checkpointing_kwargs={"use_reentrant": False},

        # Other settings
        report_to="none",
        seed=CFG.seed,
        remove_unused_columns=False,
        dataloader_num_workers=0,
        dataloader_pin_memory=True,

        # Learning rate scheduler
        lr_scheduler_type="cosine",             # Cosine decay
        lr_scheduler_kwargs={"warmup_ratio": CFG.warmup_ratio},

        # Disable unnecessary features for LoRA
        past_index=-1,
    )

    print(f"   [INFO] Total steps: {total_steps}, Warmup: {warmup_steps}")
    print(f"   [INFO] Gradient clipping: {CFG.max_grad_norm}")
    print(f"   [INFO] LR scheduler: cosine with {CFG.warmup_ratio*100}% warmup")

    # ============================================================
    # TRAINER
    # ============================================================
    print(f"   [TRAIN] Initializing trainer...")

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds if do_eval else None,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)] if do_eval else [],
    )

    # ============================================================
    # TRAIN
    # ============================================================
    print(f"   [START] Starting LoRA-only training...")
    trainer.train()

    # ============================================================
    # SAVE LoRA ADAPTER
    # ============================================================
    trainer.save_model(agent_output_dir)
    print(f"   [SAVE] LoRA adapter saved: {agent_output_dir}")

    # Also save adapter config
    adapter_config = {
        "base_model_name": CFG.model_name,
        "lora_rank": lora_rank,
        "lora_alpha": CFG.lora_alpha,
        "target_modules": CFG.target_modules,
        "learning_rate": CFG.lr,
        "epochs": CFG.epochs,
        "trainable_params": trainable_params,
        "total_params": all_param,
        "trainable_ratio": f"{100*trainable_params/all_param:.4f}%",
    }
    with open(os.path.join(agent_output_dir, "adapter_config.json"), 'w') as f:
        json.dump(adapter_config, f, indent=2)

    # ============================================================
    # HISTORY & METRICS
    # ============================================================
    history = trainer.state
    train_time_min = (time.time() - t0) / 60

    log_history = getattr(history, "log_history", []) or []
    train_loss_logs = [e for e in log_history if "loss" in e and "eval_loss" not in e]
    eval_loss_logs = [e for e in log_history if "eval_loss" in e]
    train_loss_final = train_loss_logs[-1]["loss"] if train_loss_logs else None
    eval_loss_final = eval_loss_logs[-1]["eval_loss"] if eval_loss_logs else None

    best_metric = eval_loss_final if do_eval else train_loss_final

    training_history[agent_id] = {
        'train_loss': [e["loss"] for e in train_loss_logs],
        'eval_loss': [e["eval_loss"] for e in eval_loss_logs],
        'learning_rate': [e.get("learning_rate", 0) for e in train_loss_logs],
        'train_time_min': train_time_min,
        'final_train_loss': train_loss_final,
        'final_eval_loss': eval_loss_final,
        'trainable_params': trainable_params,
        'total_params': all_param,
    }

    df_rows.append({
        'agent': agent_id,
        'lora_rank': lora_rank,
        'trainable_params': trainable_params,
        'total_params': all_param,
        'train_samples': ds['num_train'],
        'train_loss_final': train_loss_final,
        'eval_loss_final': eval_loss_final,
        'train_time_min': train_time_min,
        'best_metric': best_metric,
    })

    print(f"\n   [SUMMARY] {agent_id.upper()}")
    print(f"   Time: {train_time_min:.1f} min")
    print(f"   Train loss: {train_loss_final:.6f}")
    if eval_loss_final is not None:
        print(f"   Eval loss: {eval_loss_final:.6f}")
    print(f"   Trainable: {trainable_params:,} / {all_param:,} ({100*trainable_params/all_param:.3f}%)")

    # Cleanup
    del model, trainer, lora_config
    gc.collect()
    torch.cuda.empty_cache()

# %% Cell 8: Training History Chart (Matplotlib)
print("\n" + "=" * 70)
print("STEP 5: TRAINING HISTORY VISUALIZATION")
print("=" * 70)

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Training History (LoRA Only)', fontsize=16, fontweight='bold')

# Plot 1: Train Loss per agent
ax1 = axes[0, 0]
colors_line = plt.cm.tab10(np.linspace(0, 1, len(training_history)))
for i, (agent, hist) in enumerate(training_history.items()):
    steps = range(1, len(hist['train_loss']) + 1)
    ax1.plot(steps, hist['train_loss'], label=agent, color=colors_line[i], linewidth=2)
ax1.set_xlabel('Step')
ax1.set_ylabel('Train Loss')
ax1.set_title('Training Loss per Agent')
ax1.legend()
ax1.grid(True, alpha=0.3)

# Plot 2: Eval Loss per agent
ax2 = axes[0, 1]
has_eval = False
for i, (agent, hist) in enumerate(training_history.items()):
    if hist['eval_loss']:
        has_eval = True
        epochs = range(1, len(hist['eval_loss']) + 1)
        ax2.plot(epochs, hist['eval_loss'], label=agent, color=colors_line[i], linewidth=2, marker='o')
if has_eval:
    ax2.set_xlabel('Eval Step')
    ax2.set_ylabel('Eval Loss')
    ax2.set_title('Evaluation Loss per Agent')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
else:
    ax2.text(0.5, 0.5, 'No eval data', ha='center', va='center', transform=ax2.transAxes)

# Plot 3: Learning Rate
ax3 = axes[1, 0]
for i, (agent, hist) in enumerate(training_history.items()):
    steps = range(1, len(hist['learning_rate']) + 1)
    ax3.plot(steps, hist['learning_rate'], label=agent, color=colors_line[i], linewidth=2)
ax3.set_xlabel('Step')
ax3.set_ylabel('Learning Rate')
ax3.set_title('Learning Rate Schedule')
ax3.legend()
ax3.grid(True, alpha=0.3)
ax3.set_yscale('log')

# Plot 4: Training time bar
ax4 = axes[1, 1]
agents_list = list(training_history.keys())
times = [training_history[a]['train_time_min'] for a in agents_list]
colors_bar = plt.cm.viridis(np.linspace(0.2, 0.8, len(agents_list)))
bars = ax4.bar(agents_list, times, color=colors_bar, edgecolor='white')
ax4.set_ylabel('Time (minutes)')
ax4.set_title('Training Time per Agent')
for bar, t in zip(bars, times):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
             f'{t:.1f}m', ha='center', va='bottom', fontsize=9)

plt.tight_layout()
hist_fig_path = os.path.join(CFG.plots_dir, '03_training_history.png')
fig.savefig(hist_fig_path, bbox_inches='tight', facecolor='white')
print(f"\n[OK] Training history saved: {hist_fig_path}")
plt.show()

# %% Cell 9: Summary Dashboard (Matplotlib)
print("\n" + "=" * 70)
print("STEP 6: SUMMARY DASHBOARD")
print("=" * 70)

df_summary = pd.DataFrame(df_rows)
print("\n[TRAINING SUMMARY]")
if df_summary.empty:
    print("(No training results - all agents may have failed)")
else:
    print(df_summary.to_string(index=False))

    # Summary Matplotlib Charts
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('Training Summary Dashboard (LoRA Only)', fontsize=16, fontweight='bold')

    agents_list = df_summary['agent'].tolist()

    # Plot 1: Train Loss Final
    ax1 = axes[0, 0]
    train_losses = df_summary['train_loss_final'].tolist()
    colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(agents_list)))
    bars = ax1.bar(agents_list, train_losses, color=colors, edgecolor='white')
    ax1.set_ylabel('Train Loss')
    ax1.set_title('Final Train Loss')
    for bar, l in zip(bars, train_losses):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                 f'{l:.4f}', ha='center', va='bottom', fontsize=9)

    # Plot 2: Eval Loss Final
    ax2 = axes[0, 1]
    eval_losses = df_summary['eval_loss_final'].tolist()
    bars = ax2.bar(agents_list, eval_losses, color=colors, edgecolor='white')
    ax2.set_ylabel('Eval Loss')
    ax2.set_title('Final Eval Loss')
    for bar, l in zip(bars, eval_losses):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                 f'{l:.4f}', ha='center', va='bottom', fontsize=9)

    # Plot 3: Training Time
    ax3 = axes[0, 2]
    times = df_summary['train_time_min'].tolist()
    bars = ax3.bar(agents_list, times, color='#3498db', edgecolor='white')
    ax3.set_ylabel('Time (minutes)')
    ax3.set_title('Training Time')
    for bar, t in zip(bars, times):
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                 f'{t:.1f}m', ha='center', va='bottom', fontsize=9)

    # Plot 4: Trainable Parameters (NEW - shows LoRA efficiency)
    ax4 = axes[1, 0]
    trainable_pcts = [100*t/total for t, total in zip(df_summary['trainable_params'], df_summary['total_params'])]
    bars = ax4.bar(agents_list, trainable_pcts, color='#2ecc71', edgecolor='white')
    ax4.set_ylabel('Trainable Parameters (%)')
    ax4.set_title('LoRA Efficiency (% Trainable)')
    ax4.set_ylim(0, max(trainable_pcts) * 1.2)
    for bar, p in zip(bars, trainable_pcts):
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                 f'{p:.3f}%', ha='center', va='bottom', fontsize=8)

    # Plot 5: LoRA Rank (pie)
    ax5 = axes[1, 1]
    ranks = df_summary['lora_rank'].tolist()
    rank_counts = {}
    for a, r in zip(agents_list, ranks):
        rank_counts[r] = rank_counts.get(r, 0) + 1
    ax5.pie(list(rank_counts.values()), labels=[f'r={r}' for r in rank_counts.keys()],
             autopct='%1.0f%%', colors=plt.cm.Set2(np.linspace(0, 1, len(rank_counts))))
    ax5.set_title('LoRA Rank Distribution')

    # Plot 6: Best Metric
    ax6 = axes[1, 2]
    metrics = df_summary['best_metric'].tolist()
    bars = ax6.bar(agents_list, metrics, color='#9b59b6', edgecolor='white')
    ax6.set_ylabel('Best Metric (Loss)')
    ax6.set_title('Best Metric')
    for bar, m in zip(bars, metrics):
        ax6.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                 f'{m:.4f}', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    summary_fig_path = os.path.join(CFG.plots_dir, '04_training_summary.png')
    fig.savefig(summary_fig_path, bbox_inches='tight', facecolor='white')
    print(f"\n[OK] Summary dashboard saved: {summary_fig_path}")
    plt.show()

# %% Cell 10: Save All Results
print("\n" + "=" * 70)
print("STEP 7: SAVING ALL RESULTS")
print("=" * 70)

# Save training history
with open(os.path.join(CFG.output_dir, 'training_history.json'), 'w') as f:
    json.dump(training_history, f, indent=2, cls=NumpyEncoder)

# Save EDA results
with open(os.path.join(CFG.output_dir, 'eda_results.json'), 'w') as f:
    json.dump(eda_results, f, indent=2, cls=NumpyEncoder)

# Save feature results
with open(os.path.join(CFG.output_dir, 'feature_results.json'), 'w') as f:
    json.dump(feature_results, f, indent=2, cls=NumpyEncoder)

# Save summary CSV
df_summary.to_csv(os.path.join(CFG.output_dir, 'training_summary.csv'), index=False)

print("\n[SAVED FILES]")
print(f"   - {CFG.output_dir}/training_history.json")
print(f"   - {CFG.output_dir}/eda_results.json")
print(f"   - {CFG.output_dir}/feature_results.json")
print(f"   - {CFG.output_dir}/training_summary.csv")
print(f"   - {CFG.plots_dir}/01_eda_overview.png")
print(f"   - {CFG.plots_dir}/02_feature_analysis.png")
print(f"   - {CFG.plots_dir}/03_training_history.png")
print(f"   - {CFG.plots_dir}/04_training_summary.png")

print("\n" + "=" * 70)
print("TRAINING PIPELINE COMPLETED SUCCESSFULLY!")
print("=" * 70)
print("\n[IMPORTANT NOTES]")
print("- This training uses LoRA ONLY (no full fine-tuning)")
print("- Only LoRA adapter weights are trainable")
print("- Base model parameters are completely frozen")
print("- Lower learning rate (1e-4) for stable LoRA training")
print("- Gradient checkpointing enabled for memory efficiency")
print("=" * 70)
