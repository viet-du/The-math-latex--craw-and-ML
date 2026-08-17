# 📘 BÁO CÁO PIPELINE FINE-TUNE — Qwen2.5-Math-1.5B-Instruct + LoRA cho hệ thống 5-Agent Math Solver

> File nguồn: `train_model/qwen25_math_5agent_lora_kaggle_resume.py` (1010 dòng)
> Phiên bản: **Resume** — chỉ train `agent3, agent4, agent5` (agent1 & agent2 đã train xong từ lần trước)
> Framework: HuggingFace Transformers + PEFT (LoRA)

---

## 1️⃣ Tổng quan

Pipeline này fine-tune model **`Qwen/Qwen2.5-Math-1.5B-Instruct`** bằng kỹ thuật **LoRA (Low-Rank Adaptation)** để tạo ra **5 adapter chuyên biệt** — mỗi adapter đảm nhận một vai trò (agent) trong hệ thống giải toán đa tác vụ.

| Mục | Giá trị |
|---|---|
| **Base model** | `Qwen/Qwen2.5-Math-1.5B-Instruct` |
| **Kỹ thuật** | LoRA (Low-Rank Adaptation) |
| **Số agents tổng** | 5 (agent1 → agent5) |
| **Agents train lần này** | `agent3, agent4, agent5` |
| **Framework** | PyTorch + Transformers + PEFT |
| **Môi trường chạy** | Kaggle Notebook (GPU) |

### Mục tiêu

- **Hiệu quả**: Chỉ train ~0.3% tham số (≈4.5M / 1.5B) thay vì full fine-tune.
- **Chuyên biệt hóa**: Mỗi adapter học một vai trò riêng trong pipeline giải toán 5-agent.
- **Khả dĩ trên Kaggle**: Phù hợp với giới hạn VRAM 16GB (T4) hoặc 24GB (P100).

---

## 2️⃣ Chuẩn bị môi trường (Cell 1)

```10:34:train_model/qwen25_math_5agent_lora_kaggle_resume.py
import os, sys, re, json, time, gc, random, math
from pathlib import Path

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
```

### Các thư viện cốt lõi

| Package | Vai trò |
|---|---|
| `transformers>=4.45.0` | Model + Trainer |
| `peft>=0.13.0` | LoRA injection |
| `accelerate` | Distributed / mixed precision |
| `bitsandbytes` | 8-bit optimizer (`paged_adamw_8bit`) |
| `datasets>=3.0.0` | Dataset abstraction |

### Xử lý xung đột phiên bản PEFT ↔ torchao

Vì Kaggle pre-install torchao ở bản cũ gây xung đột với PEFT mới, code chủ động **gỡ torchao + hạ PEFT về 0.14.0**, sau đó **monkey-patch** các hàm kiểm tra `is_torchao_available` để buộc `False`:

```37:48:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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
```

```80:93:train_model/qwen25_math_5agent_lora_kaggle_resume.py
try:
    import peft.import_utils as _peft_utils
    _peft_utils.is_torchao_available = lambda: False
    print("[OK] Patched peft.import_utils.is_torchao_available -> False")
except Exception as e:
    print(f"[WARN] Patch failed: {e}")
```

> 💡 **Lý do**: PEFT 0.14/0.16 đều raise `ImportError` nếu torchao quá cũ → monkey-patch giúp skip check này.

---

## 3️⃣ Cấu hình (Cell 2)

```122:174:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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
```

### Bảng tổng hợp hyperparameters

| Nhóm | Tham số | Giá trị | Ghi chú |
|---|---|---|---|
| **Model** | `model_name` | `Qwen/Qwen2.5-Math-1.5B-Instruct` | 1.5B params |
| | `target_modules` | `q_proj, k_proj, v_proj` | Chỉ attention projections |
| **LoRA** | `r` | 32 | Rank |
| | `alpha` | 64 | → scaling factor = α/r = 2.0 |
| | `dropout` | 0.05 | |
| **Precision** | `bf16` | True | Tự fallback fp16 |
| **Optimizer** | `optim` | `paged_adamw_8bit` | Tiết kiệm VRAM |
| **Sequence** | `max_seq_len` | 1024 | |
| **Batch** | per-device | 2 | |
| | grad_accum | 8 | **effective batch = 16** |
| **Schedule** | `epochs` | 4 | |
| | `lr` | `1e-4` | Peak LR |
| | `min_lr` | `1e-5` | Cosine floor |
| | `warmup_ratio` | 5% | |
| | `weight_decay` | 0.0 | |
| | `max_grad_norm` | 1.0 | Gradient clipping |
| **Regularization** | `neftune_noise_alpha` | 5.0 | NEFTune embedding noise |
| **Memory** | `gradient_checkpointing` | True | Trade compute ↔ memory |
| **Logging** | `eval_steps` / `save_steps` | 25 | |
| | `save_total_limit` | 4 | Chỉ giữ 4 checkpoint |

### Tự động fallback precision

```177:181:train_model/qwen25_math_5agent_lora_kaggle_resume.py
if CFG.bf16 and not torch.cuda.is_bf16_supported():
    print("[INFO] bf16 not supported on this GPU, falling back to fp16")
    CFG.bf16 = False
    CFG.fp16 = True
```

### Seed reproduction

```188:195:train_model/qwen25_math_5agent_lora_kaggle_resume.py
def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

seed_everything(CFG.seed)
```

---

## 4️⃣ Chuẩn hóa dữ liệu (Cell 3)

Hàm **`format_for_chat`** chuẩn hóa mỗi record về dạng `{"messages": [user, assistant]}` vì base model (`Qwen2.5-Math-Instruct`) dùng **chat template**:

```218:272:train_model/qwen25_math_5agent_lora_kaggle_resume.py
def format_for_chat(record):
    """Normalize record into dict {messages: [user, assistant]}."""
```

Xử lý ba trường hợp:

1. **Đã đúng cấu trúc** `messages` → giữ nguyên.
2. **Content của user là dict** dạng `{"input_values": {...}, "output": "...", "solution": "..."}` → tách thành `prompt` (ghép các input_values) và `response` (solution + final answer).
3. **Content là string** → ép về chat đơn giản.

---

## 5️⃣ Load & resolve dữ liệu (Cell 4)

Vì dataset có thể nằm ở nhiều chỗ tuỳ dataset version, code thử qua một chuỗi candidate đường dẫn:

```280:330:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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
```

Hỗ trợ **2 layout**:

- **Layout A**: `base/train/{agent_id}.jsonl`, `base/test/{agent_id}.jsonl`
- **Layout B**: `base/{agent_id}_train.jsonl`, `base/{agent_id}_test.jsonl`

Hàm `_agent_file` tự chọn file đúng theo `agent_id` + `kind`:

```301:319:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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
```

Output mẫu:

```
[INFO] Data dir: /kaggle/input/datasets/vitduq/full-data13-08/5agent_final  (layout=A)
[DATA] AGENT3
   Train: 1188 | Test: 132
[DATA] AGENT4
   Train: 1188 | Test: 132
[DATA] AGENT5
   Train: 1188 | Test: 132
```

---

## 6️⃣ Tokenization với label masking (Cell 5) — phần quan trọng nhất

### Mục tiêu

- **Chỉ tính loss trên phần assistant** (không tính loss trên prompt → tránh model học vẹt câu hỏi).
- **Pad thành cùng độ dài** `max_seq_len = 1024`.

### Cách hoạt động

```373:393:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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
```

Qwen2.5-Instruct có hỗ trợ `return_assistant_tokens_mask=True` → tạo mask `[0,0,...,1,1,...]` đánh dấu **đâu là token của assistant**.

### Fallback khi tokenizer không hỗ trợ mask

```396:409:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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
```

**Chiến lược**: Gọi `apply_chat_template` 2 lần — 1 lần có prompt generation, 1 lần full — đo `prompt_len` → từ `prompt_len` trở đi là của assistant.

### Pad & tạo labels

```411:433:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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
```

**Quy tắc label**:

- Token `pad` → `label = -100` (bỏ qua khi tính loss)
- Token thuộc prompt (assistant_mask = 0) → `label = -100`
- Token thuộc assistant (assistant_mask = 1) → `label = input_id` (tính loss)

### Kết quả sau tokenize cho mỗi agent

```
[OK] agent3: 1188 train, 132 test
[OK] agent4: 1188 train, 132 test
[OK] agent5: 1188 train, 132 test
```

---

## 7️⃣ Custom Collator (Cell 6)

Mặc dù đã pad ở bước trước, code dùng collator tự viết để **đảm bảo an toàn** (pad lại lần nữa theo độ dài lớn nhất trong batch):

```510:528:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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
```

---

## 8️⃣ Vòng lặp training (Cell 8) — phần lõi

### 8.1 Khởi tạo cho từng agent

```553:562:train_model/qwen25_math_5agent_lora_kaggle_resume.py
for agent_id in CFG.active_agents:
    if agent_id not in tokenized_datasets:
        continue

    lora_rank = CFG.lora_r.get(agent_id, 32)
    agent_output_dir = os.path.join(CFG.output_dir, agent_id)

    print(f"\n{'='*70}")
    print(f"[TRAIN] {agent_id.upper()} (LoRA r={lora_rank}, alpha={CFG.lora_alpha}, lr={CFG.lr} -> {CFG.min_lr})")
    print(f"{'='*70}")

    t0 = time.time()
```

### 8.2 Load model base & freeze toàn bộ

```566:582:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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
```

### 8.3 Inject LoRA

```584:604:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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
```

**LoRA scaling**: `scaling = lora_alpha / r = 64 / 32 = 2.0`

→ Công thức LoRA: `W_new = W_base + (B @ A) * scaling`, với `A ∈ R^{r × d_in}`, `B ∈ R^{d_out × r}`.

### 8.4 Kích hoạt NEFTune

NEFTune (Noisy Embedding Fine-Tuning) thêm noise vào embedding trong training để cải thiện generalization:

```606:612:train_model/qwen25_math_5agent_lora_kaggle_resume.py
# Enable NEFTune
if CFG.neftune_noise_alpha is not None and CFG.neftune_noise_alpha > 0:
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    else:
        for p in model.get_input_embeddings().parameters():
            p.requires_grad = True
```

> 🔬 NEFTune được kích hoạt tự động bởi Trainer thông qua tham số `neftune_noise_alpha=5.0`.

### 8.5 Tính toán steps

```620:623:train_model/qwen25_math_5agent_lora_kaggle_resume.py
steps_per_epoch = max(1, len(train_ds) // (CFG.per_device_batch_size * CFG.grad_accum))
total_steps     = steps_per_epoch * CFG.epochs
warmup_steps    = max(1, int(CFG.warmup_ratio * total_steps))
```

Với 1188 train samples:

```
steps_per_epoch = 1188 // 16 = 74
total_steps     = 74 × 4 = 296
warmup_steps    = ⌊0.05 × 296⌋ = 14
```

→ Eval mỗi **25 steps** → có 4 epoch × 74 step = ~12 lần eval.

### 8.6 Version-safe TrainingArguments

```625:677:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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
```

> ⚠️ Đoạn này dùng `inspect` để **lọc tự động các tham số không được hỗ trợ** trong phiên bản transformers đang chạy → code chạy ổn định trên cả transformers 4.x cũ lẫn mới.

### 8.7 Cấu hình early stopping

```685:691:train_model/qwen25_math_5agent_lora_kaggle_resume.py
_trainer_kwargs = dict(
    model=model,
    args=training_args,
    train_dataset=train_ds,
    eval_dataset=eval_ds if do_eval else None,
    data_collator=DataCollatorForCausalLM(tokenizer),
    callbacks=([EarlyStoppingCallback(early_stopping_patience=5), LRLogger()] if do_eval else [LRLogger()]),
)
```

- **EarlyStopping với patience=5**: dừng nếu eval_loss không cải thiện sau 5 lần eval liên tiếp (~5×25 = 125 steps).
- **LRLogger** là callback trống (giữ chỗ cho tương lai).

### 8.8 Trainer.train() & Save

```699:706:train_model/qwen25_math_5agent_lora_kaggle_resume.py
# Train
print(f"   [START] Starting training...")
trainer.train()

# Save final adapter
trainer.save_model(agent_output_dir)
print(f"   [SAVE] Adapter saved: {agent_output_dir}")
```

Sau khi train xong, `trainer.save_model` lưu **chỉ adapter** (~30MB) chứ không lưu cả base model.

### 8.9 Lưu adapter_config kèm metadata

```708:723:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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
```

### 8.10 Tổng hợp kết quả + giải phóng VRAM

```725:785:train_model/qwen25_math_5agent_lora_kaggle_resume.py
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

df_rows.append({...})

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
```

> 🧹 `del + gc.collect + empty_cache` rất quan trọng để **train nối tiếp 3 agents** trong cùng 1 session mà không tràn VRAM.

---

## 9️⃣ Visualization (Cell 9-10)

### Biểu đồ Training History (Cell 9)

```792:848:train_model/qwen25_math_5agent_lora_kaggle_resume.py
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Training History (agent3, agent4, agent5)', fontsize=16, fontweight='bold')

# Plot 1: Train loss
# Plot 2: Eval loss
# Plot 3: Learning rate (log scale + min_lr marker)
# Plot 4: Training time per agent
```

4 subplot:
1. **Training loss** theo step cho từng agent
2. **Evaluation loss** (có marker tròn)
3. **Learning rate schedule** (log-scale, đường `min_lr` màu đỏ)
4. **Training time** (bar chart)

Output: `plots/03_training_history.png`

### Summary Dashboard (Cell 10)

Load thêm `adapter_config.json` của `agent1, agent2` đã có sẵn → merge vào bảng tổng → vẽ 6 biểu đồ tổng quan:

```894:963:train_model/qwen25_math_5agent_lora_kaggle_resume.py
fig, axes = plt.subplots(2, 3, figsize=(18, 12))
fig.suptitle('Training Summary Dashboard (All 5 Agents)', fontsize=16, fontweight='bold')
```

| Subplot | Nội dung |
|---|---|
| (0,0) | Final train loss |
| (0,1) | Best eval loss |
| (0,2) | Training time (phút) |
| (1,0) | LoRA efficiency (% trainable params) |
| (1,1) | LoRA rank distribution (pie) |
| (1,2) | Train samples per agent |

Output: `plots/04_training_summary.png` + `outputs/training_summary.csv`

---

## 🔟 Lưu kết quả cuối (Cell 11)

```972:1009:train_model/qwen25_math_5agent_lora_kaggle_resume.py
# Merge new history with existing (agent1, 2 từ lần trước)
existing_history.update(training_history)
with open(history_path, 'w') as f:
    json.dump(existing_history, f, indent=2, cls=NumpyEncoder)

df_summary.to_csv(summary_fig_path.replace('.png', '.csv')
                   .replace(CFG.plots_dir, CFG.output_dir), index=False)

# Cuối cùng: kiểm tra adapter của từng agent
for agent_id in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
    agent_dir = os.path.join(CFG.output_dir, agent_id)
    adapter_file = os.path.join(agent_dir, "adapter_model.safetensors")
    if os.path.exists(adapter_file):
        size_mb = os.path.getsize(adapter_file) / (1024 * 1024)
        print(f"   ✅ {agent_id}: adapter_model.safetensors ({size_mb:.1f} MB)")
    else:
        print(f"   ❌ {agent_id}: CHƯA TRAIN / CHƯA CÓ WEIGHTS")
```

---

## 📂 Cấu trúc output

```
/kaggle/working/
├── outputs/
│   ├── agent1/
│   │   ├── adapter_config.json
│   │   ├── adapter_model.safetensors
│   │   └── checkpoint-*/...
│   ├── agent2/
│   ├── agent3/   ← train lần này
│   ├── agent4/   ← train lần này
│   ├── agent5/   ← train lần này
│   ├── training_history.json        (tổng hợp cả 5 agents)
│   └── training_summary.csv
└── plots/
    ├── 03_training_history.png
    └── 04_training_summary.png
```

---

## 📊 Tổng kết pipeline

### Đặc điểm kỹ thuật chính

| Khía cạnh | Lựa chọn | Lý do |
|---|---|---|
| **Method** | LoRA (rank=32, α=64) | Giảm VRAM, multi-adapter dễ |
| **Target modules** | `q_proj, k_proj, v_proj` | Đủ hiệu quả, ít params |
| **Precision** | bf16 (tự fallback fp16) | Tốc độ + ổn định số học |
| **Optimizer** | `paged_adamw_8bit` | Tiết kiệm optimizer state memory |
| **Memory trick** | `gradient_checkpointing` | Giảm activation memory |
| **Regularization** | NEFTune α=5.0 | Cải thiện generalization |
| **Label masking** | Chỉ tính loss trên assistant | Đúng chuẩn instruction tuning |
| **LR schedule** | `cosine_with_min_lr` | Mượt, có floor tránh LR=0 |
| **Eval strategy** | Mỗi 25 steps + early stopping | Bám sát diễn biến |
| **Checkpointing** | Lưu top-4 + best | Tránh đầy disk |

### Số liệu ước tính cho mỗi agent

| Metric | Ước lượng |
|---|---|
| Train samples | 1188 |
| Steps/epoch | 74 |
| Total steps | 296 |
| Eval events | ~12 |
| Trainable params | ~4.5M (0.3%) |
| Adapter size | ~18-30 MB (safetensors) |
| Time/agent (ước lượng trên T4) | ~25-35 phút |

### Những điểm tinh tế trong code

1. **Monkey-patch PEFT** để tránh xung đột torchao → code chạy được trên Kaggle pre-built.
2. **`inspect.signature` filter** → tương thích mọi phiên bản `transformers`.
3. **Fallback 3 lớp cho label mask** (assistant_tokens_mask → prompt-length diff → không mask) → robust.
4. **Data layout resolver** → chạy được trên nhiều vị trí dataset khác nhau.
5. **`gc.collect() + empty_cache()` giữa các agent** → train nối tiếp 3 agent không OOM.
6. **`load_best_model_at_end=True`** → luôn giữ checkpoint tốt nhất.

---

## 🎯 Kết luận

Pipeline này thể hiện một **chiến lược fine-tune hiệu quả & kinh tế**:

- **Hiệu quả**: Chỉ 0.3% params trainable, mỗi adapter khoảng 30MB.
- **Linh hoạt**: 5 adapter cho 5 vai trò → dễ tổng hợp trong inference đa-agent.
- **Robust**: Code xử lý nhiều edge case (xung đột phiên bản, layout data khác nhau, fallback precision).
- **Có thể resume**: Cấu trúc cho phép train `agent1, agent2` ở session trước, `agent3, agent4, agent5` ở session sau mà vẫn tổng hợp đầy đủ kết quả.

Khi inference, ta sẽ:
- Load base model `Qwen2.5-Math-1.5B-Instruct`.
- Với mỗi bước trong pipeline 5-agent, swap adapter tương ứng (`agent1.safetensors`, ..., `agent5.safetensors`).
- Điều này cho phép **1 base model duy nhất + 5 adapter nhỏ** phục vụ toàn bộ hệ giải toán.
