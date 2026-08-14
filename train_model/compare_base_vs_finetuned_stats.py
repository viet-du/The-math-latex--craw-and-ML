"""
train_model/compare_base_vs_finetuned_stats.py
Compare BASE Qwen2.5-Math-1.5B-Instruct vs FINE-TUNED LoRA (5-agent adapter)
on a probability/statistics problem.

Problem: "Một hộp có 5 bi đỏ và 3 bi xanh. Lấy ngẫu nhiên 2 bi (không hoàn lại).
Tính xác suất để cả 2 bi đều đỏ. Nếu biết bi thứ nhất đỏ, tính xác suất bi thứ hai cũng đỏ."
"""
import os
import sys
import torch
from datetime import datetime
from pathlib import Path

# Force UTF-8
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import importlib.util
spec = importlib.util.spec_from_file_location("inf_vi", "train_model/inference_vietnamese.py")
inf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inf)

PROBLEM = (
    "Một hộp có 5 bi đỏ và 3 bi xanh. Lấy ngẫu nhiên 2 bi không hoàn lại. "
    "a) Tính xác suất để cả 2 bi đều đỏ. "
    "b) Nếu biết bi thứ nhất là bi đỏ, tính xác suất bi thứ hai cũng là bi đỏ."
)
ADAPTER_DIR = inf.CFG.adapter_path

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[INFO] Device: {DEVICE}")
print(f"[INFO] Adapter dir: {ADAPTER_DIR} (exists={os.path.isdir(ADAPTER_DIR)})")
print(f"[INFO] Problem: {PROBLEM}\n")

from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

print("[1/3] Loading base model Qwen/Qwen2.5-Math-1.5B-Instruct...")
tokenizer = AutoTokenizer.from_pretrained(inf.CFG.base_model_name)
base_model = AutoModelForCausalLM.from_pretrained(
    inf.CFG.base_model_name,
    torch_dtype=torch.float32 if DEVICE == "cpu" else torch.float16,
    device_map=DEVICE,
)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token


def run_pipeline(model, tokenizer, problem, label):
    print(f"\n{'='*70}\n  PIPELINE: {label}\n{'='*70}")
    results = {}
    for agent_id, agent_prompt in inf.AGENT_PROMPTS.items():
        cap = inf.CFG.agent_token_caps.get(agent_id, inf.CFG.agent_max_tokens)
        messages = [
            {"role": "system", "content": agent_prompt},
            {"role": "user", "content": problem},
        ]
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=cap,
                do_sample=False,
                repetition_penalty=inf.CFG.repetition_penalty,
                no_repeat_ngram_size=inf.CFG.no_repeat_ngram_size,
                pad_token_id=tokenizer.pad_token_id,
            )
        response = tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        ).strip()
        results[agent_id] = response
        print(f"\n🔵 {agent_id.upper()} (cap={cap} tokens):\n{response}\n")
    return results


# === PIPELINE A: BASE MODEL ===
print("\n[2/3] Running BASE model...")
base_results = run_pipeline(base_model, tokenizer, PROBLEM,
                             "BASE Qwen2.5-Math-1.5B-Instruct (no fine-tuning)")

# === PIPELINE B: FINE-TUNED ===
print("\n[3/3] Running FINE-TUNED model...")
ft_results = {}
adapter_loaded = False
sub_adapters = []

if os.path.isdir(ADAPTER_DIR):
    # Try single combined adapter first
    try:
        ft_model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
        ft_results = run_pipeline(ft_model, tokenizer, PROBLEM,
                                   "FINE-TUNED 5-agent LoRA")
        adapter_loaded = True
    except Exception as e:
        print(f"[INFO] Combined adapter load failed: {e}")
        # Try per-agent sub-adapters
        sub_adapters = sorted([d for d in Path(ADAPTER_DIR).iterdir()
                               if d.is_dir() and d.name.startswith("agent")])
        if sub_adapters:
            print(f"[INFO] Found sub-adapters: {[s.name for s in sub_adapters]}")
            ft_results = {}
            current_model = base_model
            for sub_dir in sub_adapters:
                agent_id = sub_dir.name
                try:
                    current_model = PeftModel.from_pretrained(base_model, str(sub_dir))
                except Exception as ee:
                    print(f"[WARN] Could not load {agent_id}: {ee}")
                    ft_results[agent_id] = f"[adapter load failed: {ee}]"
                    continue
                cap = inf.CFG.agent_token_caps.get(agent_id, inf.CFG.agent_max_tokens)
                messages = [
                    {"role": "system", "content": inf.AGENT_PROMPTS[agent_id]},
                    {"role": "user", "content": PROBLEM},
                ]
                prompt = tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True)
                inputs = tokenizer(prompt, return_tensors="pt").to(current_model.device)
                with torch.no_grad():
                    outputs = current_model.generate(
                        **inputs,
                        max_new_tokens=cap,
                        do_sample=False,
                        repetition_penalty=inf.CFG.repetition_penalty,
                        no_repeat_ngram_size=inf.CFG.no_repeat_ngram_size,
                        pad_token_id=tokenizer.pad_token_id,
                    )
                response = tokenizer.decode(
                    outputs[0][inputs["input_ids"].shape[1]:],
                    skip_special_tokens=True).strip()
                ft_results[agent_id] = response
                print(f"\n🟢 {agent_id.upper()} (cap={cap} tokens):\n{response}\n")
                # Unload to load next
                try:
                    current_model = current_model.unload()
                except Exception:
                    base_model = current_model  # fallback
                adapter_loaded = True

if not adapter_loaded:
    print(f"[ERROR] No adapter found at {ADAPTER_DIR}.")
    print("Skipping fine-tuned pipeline.")

# === COMPARISON TABLE ===
print("\n" + "="*70)
print("  COMPARISON TABLE (first 80 chars per agent)")
print("="*70)
header = f"{'Agent':<10} | {'BASE':<42} | {'FINETUNED':<42}"
print(header)
print("-" * len(header))
for agent_id in inf.AGENT_PROMPTS:
    b = base_results.get(agent_id, "(none)")
    f = ft_results.get(agent_id, "(no adapter)")
    b_short = (b[:40] + "..") if len(b) > 42 else b
    f_short = (f[:40] + "..") if len(f) > 42 else f
    print(f"{agent_id:<10} | {b_short:<42} | {f_short:<42}")

# === SAVE LOG ===
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
log_dir = Path("archive/logs")
log_dir.mkdir(parents=True, exist_ok=True)
log_path = log_dir / f"compare_stats_{ts}.log"
with open(log_path, "w", encoding="utf-8") as f:
    f.write(f"Problem: {PROBLEM}\n\n")
    f.write("="*70 + "\nPIPELINE A: BASE MODEL\n" + "="*70 + "\n")
    for k, v in base_results.items():
        f.write(f"\n{k}:\n{v}\n")
    if ft_results:
        f.write("\n" + "="*70 + "\nPIPELINE B: FINE-TUNED\n" + "="*70 + "\n")
        for k, v in ft_results.items():
            f.write(f"\n{k}:\n{v}\n")
    f.write("\n" + "="*70 + "\nCOMPARISON (first 100 chars)\n" + "="*70 + "\n")
    for agent_id in inf.AGENT_PROMPTS:
        f.write(f"\n[{agent_id}]\n")
        f.write(f"  BASE: {base_results.get(agent_id, '(none)')[:100]}\n")
        f.write(f"  FT:   {ft_results.get(agent_id, '(no adapter)')[:100]}\n")
print(f"\n✅ Saved log: {log_path}")
print("Done.")