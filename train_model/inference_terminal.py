"""
5-Agent Math Solver - Inference Script (Terminal Only)
======================================================
Khong co HTML. Chi in ra terminal thuan tuy de de doc.
"""

import os, re, gc, time, json, sys
import torch
import numpy as np

# ══════════════════════════════════════════════════════════════
# CELL 1: Setup
# ══════════════════════════════════════════════════════════════
def setup():
    print("Setting up...")
    import subprocess
    for pkg in ["torchao"]:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "uninstall", "-y", pkg],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    for pkg in ["transformers>=4.45.0", "peft>=0.13.0", "accelerate", "bitsandbytes>=0.46.1"]:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg],
                                  stdout=subprocess.DEVNULL)
        except Exception:
            pass

    print("Done.")

setup()

from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

# ══════════════════════════════════════════════════════════════
# CELL 2: Config
# ══════════════════════════════════════════════════════════════
class CFG:
    base_model_name = "Qwen/Qwen2.5-Math-1.5B-Instruct"
    adapter_path    = "/kaggle/input/datasets/vitduq/train-modle317/outputs"
    max_new_tokens  = 512
    temperature     = 0.5
    top_p           = 0.9
    use_finetuned   = True
    use_quantization = False
    agent_max_tokens = 512

AGENT_PROMPTS = {
    "agent1": (
        "Ban la Agent 1 (Normalizer & Translator). "
        "Nhiem vu: doc yeu cau toan hoc, lam sach cau chu tieng Viet "
        "va chuan hoa tat ca bieu thuc toan sang dang LaTeX chuan ($...$ hoac $$...$$)."
    ),
    "agent2": (
        "Ban la Agent 2 (Classifier & Constraint Parser). "
        "Nhiem vu: nhan dien phan loai bai toan, muc do kho, "
        "danh sach bien so va cac dieu kien rang buoc xac dinh."
    ),
    "agent3": (
        "Ban la Agent 3 (Core Reasoning Solver). "
        "Nhiem vu: trinh bay logic giai toan trung gian, cac buoc suy luan "
        "va phuong phap ap dung de giai bai toan."
    ),
    "agent4": (
        "Ban la Agent 4 (Formatter & Boxed Engine). "
        "Nhiem vu: trinh bay loi giai chi tiet 5 buoc bang tieng Viet tu nhien "
        "va BAT BUOC ket luan dap an cuoi cung trong khung \\boxed{}."
    ),
    "agent5": (
        "Ban la Agent 5 (Verifier & Guardrail). "
        "Nhiem vu: kiem tra loi giai toan: loai bo tieng Trung/Anh lot vao, "
        "kiem tra ngoac LaTeX $...$ va xac nhan dap an \\boxed{} chinh xac."
    ),
}

STEP_NAMES = {
    "agent1": "CHUAN HOA",
    "agent2": "PHAN LOAI",
    "agent3": "SUY LUAN",
    "agent4": "LOI GIAI",
    "agent5": "XAC MINH",
}

# ══════════════════════════════════════════════════════════════
# CELL 3: Load Model
# ══════════════════════════════════════════════════════════════
def load_model_tokenizer(use_finetuned=True):
    print("Loading tokenizer...")
    tok = AutoTokenizer.from_pretrained(CFG.base_model_name, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    print("Loading base model...")
    model_kwargs = {"device_map": "auto", "trust_remote_code": True}

    if CFG.use_quantization:
        try:
            bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
            model = AutoModelForCausalLM.from_pretrained(
                CFG.base_model_name, dtype=torch.float16, quantization_config=bnb, **model_kwargs
            )
            print("  [OK] 4-bit quantization")
        except Exception as e:
            print(f"  [WARN] bnb failed ({e}), loading without quantization")
            model = AutoModelForCausalLM.from_pretrained(
                CFG.base_model_name, dtype=torch.float16, **model_kwargs
            )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            CFG.base_model_name, dtype=torch.float16, **model_kwargs
        )

    adapters = None
    if use_finetuned and os.path.exists(CFG.adapter_path):
        print("Loading fine-tuned adapters...")
        found = {}
        for root, _dirs, files in os.walk(CFG.adapter_path):
            if "adapter_config.json" in files:
                for a in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
                    if a in root.lower():
                        found[a] = root
                        break
        adapters = found

        if found:
            first = list(found.keys())[0]
            ft_model = PeftModel.from_pretrained(model, found[first], adapter_name=first)
            for aid, path in found.items():
                if aid != first:
                    ft_model.load_adapter(path, adapter_name=aid)
            print(f"  Loaded adapters: {list(found.keys())}")
            model = ft_model

    model.eval()
    return model, tok, adapters

# ══════════════════════════════════════════════════════════════
# CELL 4: Run Agent
# ══════════════════════════════════════════════════════════════
def run_agent(model, tok, agent_id, user_input, adapters=None):
    if adapters and agent_id in adapters and hasattr(model, "set_adapter"):
        model.set_adapter(agent_id)

    messages = [
        {"role": "system", "content": AGENT_PROMPTS[agent_id]},
        {"role": "user",   "content": user_input},
    ]

    prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=CFG.agent_max_tokens,
            do_sample=False,
            pad_token_id=tok.pad_token_id,
        )

    return tok.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()

# ══════════════════════════════════════════════════════════════
# CELL 5: Extract Answer
# ══════════════════════════════════════════════════════════════
def extract_answer(text):
    if not text:
        return None
    matches = re.findall(r'\\boxed\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', text)
    return matches[-1].strip() if matches else None

# ══════════════════════════════════════════════════════════════
# CELL 6: Solve Problem
# ══════════════════════════════════════════════════════════════
def solve(model, tok, problem, adapters=None):
    W = 72
    SEP = "=" * W
    MID = "-" * W

    print(f"\n{SEP}")
    print(f"  DE BAI")
    print(f"{SEP}")
    print(wrap(f"  {problem}", W))

    ctx = {}
    t0 = time.time()

    # Agent 1
    out1 = run_agent(model, tok, "agent1", problem, adapters)
    ctx["agent1"] = out1
    print(f"\n{MID}")
    print(f"  [1/5] {STEP_NAMES['agent1']}")
    print(MID)
    print(wrap(out1, W))

    # Agent 2
    out2 = run_agent(model, tok, "agent2", out1, adapters)
    ctx["agent2"] = out2
    print(f"\n{MID}")
    print(f"  [2/5] {STEP_NAMES['agent2']}")
    print(MID)
    print(wrap(out2, W))

    # Agent 3
    history3 = f"De bai: {problem}\n\nChuan hoa: {out1}\n\nPhan loai: {out2}"
    out3 = run_agent(model, tok, "agent3", history3, adapters)
    ctx["agent3"] = out3
    print(f"\n{MID}")
    print(f"  [3/5] {STEP_NAMES['agent3']}")
    print(MID)
    print(wrap(out3, W))

    # Agent 4
    sol4_in = f"De: {problem}\n\nSuy luan:\n{out3}"
    out4 = run_agent(model, tok, "agent4", sol4_in, adapters)
    ctx["agent4"] = out4
    print(f"\n{MID}")
    print(f"  [4/5] {STEP_NAMES['agent4']}")
    print(MID)
    print(wrap(out4, W))

    # Agent 5
    verify_in = f"Loi giai:\n{out4}"
    out5 = run_agent(model, tok, "agent5", verify_in, adapters)
    ctx["agent5"] = out5
    print(f"\n{MID}")
    print(f"  [5/5] {STEP_NAMES['agent5']}")
    print(MID)
    print(wrap(out5, W))

    # Final answer
    answer = extract_answer(out4) or extract_answer(out5) or extract_answer(out3)
    elapsed = time.time() - t0

    print(f"\n{SEP}")
    print(f"  DAP AN CUOI CUNG")
    print(f"{SEP}")
    if answer:
        print(f"\n  \\boxed{{{answer}}}\n")
    else:
        print("  [Khong tim thay \\boxed{} trong loi giai]\n")

    print(f"  Thoi gian: {elapsed:.1f}s")
    print(SEP)

    return answer, elapsed, ctx

# ══════════════════════════════════════════════════════════════
# CELL 7: Eval & Summary
# ══════════════════════════════════════════════════════════════
def normalize_answer(ans):
    if ans is None:
        return None
    ans = str(ans).strip()
    ans = re.sub(r'\\boxed\{|\}', '', ans)
    ans = re.sub(r'\\displaystyle', '', ans)
    ans = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'(\1)/(\2)', ans)
    ans = re.sub(r'\\sqrt\{([^{}]+)\}', r'sqrt(\1)', ans)
    ans = re.sub(r'\\cdot|\\times', '*', ans)
    ans = re.sub(r'\\div|/', '/', ans)
    ans = re.sub(r'\\\w+', '', ans)
    ans = re.sub(r'[{}]', '', ans)
    ans = ans.replace(' ', '')
    return ans

class Evaluator:
    def __init__(self):
        self.results = []

    def record(self, problem, answer, elapsed, ground_truth=None):
        has_box = answer is not None
        # latex score
        score = 0.0
        if answer and '$' in answer or answer and '\\' in answer:
            score += 0.5
        if answer and '\\boxed{' in answer:
            score += 0.5
        # vn score
        if answer:
            letters = [c for c in answer if c.isalpha()]
            vn = sum(1 for c in letters if ord(c) > 127) / len(letters) if letters else 0
        else:
            vn = 0

        r = {
            'problem': problem[:80],
            'answer': answer,
            'has_answer': has_box,
            'latex_score': score,
            'vn_score': min(1.0, vn * 2),
            'time_sec': elapsed,
        }
        if ground_truth:
            p = normalize_answer(answer)
            t = normalize_answer(ground_truth)
            r['exact_match'] = 1.0 if p and p == t else 0.0
        self.results.append(r)
        return r

    def summary(self):
        if not self.results:
            return {}
        n = len(self.results)
        has_ans = sum(1 for r in self.results if r['has_answer'])
        avg_latex = sum(r['latex_score'] for r in self.results) / n
        avg_vn = sum(r['vn_score'] for r in self.results) / n
        avg_time = sum(r['time_sec'] for r in self.results) / n
        em = None
        if 'exact_match' in self.results[0]:
            em = sum(r['exact_match'] for r in self.results) / n
        return {
            'total': n, 'has_answer': has_ans,
            'answer_rate': has_ans / n * 100,
            'latex_score': avg_latex,
            'vn_score': avg_vn,
            'avg_time': avg_time,
            'exact_match': em,
        }

    def print_report(self):
        s = self.summary()
        W = 72
        SEP = "=" * W
        print(f"\n{SEP}")
        print(f"  BAO CAO DANH GIA")
        print(SEP)
        print(f"  Tong bai:          {s['total']}")
        print(f"  Co dap an:         {s['has_answer']} ({s['answer_rate']:.1f}%)")
        print(f"  LaTeX quality:     {s['latex_score']:.3f}/1.0")
        print(f"  Tieng Viet:        {s['vn_score']:.3f}/1.0")
        print(f"  Thoi gian TB:      {s['avg_time']:.1f}s")
        if s['exact_match'] is not None:
            print(f"  Exact Match:       {s['exact_match']*100:.1f}%")
        print(SEP)

    def save(self, path):
        import pandas as pd
        pd.DataFrame(self.results).to_csv(path, index=False, encoding='utf-8')
        print(f"  Saved: {path}")

# ══════════════════════════════════════════════════════════════
# CELL 8: Helpers
# ══════════════════════════════════════════════════════════════
def wrap(text, width=72, indent=2):
    """Wrap text to terminal width, preserve line breaks."""
    if not text:
        return ""
    lines_out = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            lines_out.append("")
            continue
        words = line.split()
        cur = " " * indent
        cur_len = indent
        for w in words:
            if cur_len + len(w) + 1 <= width:
                cur += w + " "
                cur_len += len(w) + 1
            else:
                lines_out.append(cur.rstrip())
                cur = " " * indent + w + " "
                cur_len = indent + len(w) + 1
        if cur.strip():
            lines_out.append(cur.rstrip())
    return "\n".join(lines_out)

# ══════════════════════════════════════════════════════════════
# CELL 9: Demo
# ══════════════════════════════════════════════════════════════
def main():
    W = 72
    SEP = "=" * W
    print(f"\n{SEP}")
    print(f"  5-AGENT MATH SOLVER (Terminal)")
    print(f"  Base: {CFG.base_model_name}")
    print(SEP)

    model, tok, adapters = load_model_tokenizer(CFG.use_finetuned)
    mode = "FINE-TUNED" if adapters else "BASE MODEL"
    print(f"\n  Model: {mode}")
    if adapters:
        print(f"  Adapters: {list(adapters.keys())}")

    test_problems = [
        "Giai phuong trinh: $x^2 - 5x + 6 = 0$",
        "Tinh dao ham: $f(x) = x^3 + 2x^2 - x + 1$",
        "Cho $a = 3$, $b = 4$. Tinh $\\sqrt{a^2 + b^2}$",
    ]

    ev = Evaluator()
    for i, prob in enumerate(test_problems, 1):
        print(f"\n{'#' * W}")
        print(f"  BAI {i}/{len(test_problems)}")
        print('#' * W)
        ans, elapsed, _ = solve(model, tok, prob, adapters)
        ev.record(prob, ans, elapsed)
        gc.collect()
        torch.cuda.empty_cache()

    ev.print_report()
    out_path = "/kaggle/working/eval_results.csv"
    ev.save(out_path)

    print(f"\n{SEP}")
    print("  HOAN THANH!")
    print(SEP)

if __name__ == "__main__":
    main()
