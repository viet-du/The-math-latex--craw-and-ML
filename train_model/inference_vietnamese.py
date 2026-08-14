"""
VIETNAMESE MATH SOLVER - INFERENCE SCRIPT
==========================================
Input: Bài toán tiếng Việt
Output: Lời giải từng bước bằng tiếng Việt với \boxed{}

Sử dụng:
    python inference_vietnamese.py --problem "Một người có 50 quả táo..."

Hoặc chạy interactive:
    python inference_vietnamese.py --interactive

    Hoặc so sánh BASE vs FINE-TUNED trên cùng 1 bài toán:
    python inference_vietnamese.py --compare
    python inference_vietnamese.py --compare --problem "Một hộp có 5 bi đỏ..."
"""

import argparse
import json
import os
import re
import sys
import gc
import torch
from datetime import datetime
from pathlib import Path

# Force UTF-8 stdout/stderr để in được tiếng Việt trên Windows (cp1252) console
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# =============================================================================
# CONFIGURATION - CẬP NHẬT ĐƯỜNG DẪN THEO MÔI TRƯỜNG CỦA BẠN
# =============================================================================
class CFG:
    # Base model
    base_model_name = "Qwen/Qwen2.5-Math-1.5B-Instruct"
    
    # LoRA adapters (thay đổi theo đường dẫn của bạn)
    # Sau khi train xong, adapters sẽ nằm ở output_dir/agent{1-5}/
    adapter_path = "./outputs"  # Thư mục chứa 5 adapters
    
    # Generation settings
    max_new_tokens = 384  # Tăng từ 256 để tránh cắt giữa chừng
    agent_max_tokens = 384

    # Repetition control (Fix mode-collapse: tăng rep_penalty & ngram size)
    repetition_penalty = 1.5
    no_repeat_ngram_size = 6

    # Per-agent token caps (tăng để fine-tuned có đủ chỗ viết tiếng Việt)
    agent_token_caps = {
        "agent1": 256,
        "agent2": 96,
        "agent3": 512,
        "agent4": 384,
        "agent5": 192,
    }
    
    # Mode
    use_finetuned = True  # True = dùng LoRA, False = base model
    
    # Quantization (nếu cần giảm bộ nhớ)
    use_quantization = False
    
    # Device
    device = "cuda" if torch.cuda.is_available() else "cpu"


# =============================================================================
# PROMPTS - BẮT BUỘC TIẾNG VIỆT (KHỚP 100% VỚI TRAINING DATA!)
# =============================================================================
AGENT_PROMPTS = {
    "agent1": (
        "Bạn là Agent 1 - Chuẩn hóa bài toán.\n"
        "Nhiệm vụ: Viết lại bài toán dưới dạng LaTeX chuẩn.\n"
        "QUY TẮC:\n"
        "- Xuất MỖI bài toán đã chuẩn hóa, KHÔNG giải\n"
        "- Dùng \\(...) cho inline math, \\[...\\] cho display math\n"
        "- Giữ nguyên ý nghĩa toán học\n"
        "- Tiếng Việt cho phần text"
    ),
    "agent2": (
        "Bạn là Agent 2 - Phân loại bài toán.\n"
        "Nhiệm vụ: Xác định loại bài toán.\n"
        "QUY TẮC:\n"
        "- Xuất đúng 1 dòng theo format: [Chủ đề] | [Loại] | [Độ khó]\n"
        "- Ví dụ: Phân số | Tính toán | Trung bình\n"
        "- Chủ đề: Phân số, Hình học, Đại số, Tỉ lệ, Phần trăm, Căn bậc hai, Đạo hàm\n"
        "- Loại: Tính toán, Chứng minh, Ứng dụng, Quy hoạch\n"
        "- Độ khó: Dễ, Trung bình, Khó"
    ),
    "agent3": (
        "Bạn là Agent 3 - Suy luận giải toán.\n"
        "Nhiệm vụ: Giải bài toán từng bước.\n"
        "QUY TẮC:\n"
        "- Mỗi bước: (1) Làm gì, (2) Áp dụng công thức gì, (3) Kết quả\n"
        "- Dùng tiếng Việt hoàn toàn cho giải thích\n"
        "- Dùng LaTeX cho công thức toán học\n"
        "- Viết rõ ràng, logic từng bước"
    ),
    "agent4": (
        "Bạn là Agent 4 - Trình bày lời giải hoàn chỉnh.\n"
        "Nhiệm vụ: Viết lời giải hoàn chỉnh, chuyên nghiệp.\n"
        "QUY TẮC:\n"
        "- Viết các bước theo thứ tự logic\n"
        "- Mỗi bước: (1) Ghi công thức, (2) Thay số, (3) Tính toán, (4) Kết quả\n"
        "- Cuối cùng phải có đáp án trong \\boxed{...}\n"
        "- Dùng tiếng Việt cho toàn bộ text\n"
        "- Dùng LaTeX cho công thức"
    ),
    "agent5": (
        "Bạn là Agent 5 - Kiểm tra và xác nhận đáp án.\n"
        "Nhiệm vụ: Xác minh lời giải cuối cùng.\n"
        "QUY TẮC BẮT BUỘC:\n"
        "- CHỈ xuất DUY NHẤT MỘT dòng theo format:\n"
        "  'Dap an dung: \\boxed{đáp án}'\n"
        "- KHÔNG tính thêm đạo hàm cấp cao\n"
        "- KHÔNG lặp lại các bước trước\n"
        "- KHÔNG xuất thêm dòng nào khác\n"
        "- Dùng tiếng Việt cho phần text"
    ),
}


# =============================================================================
# MODEL LOADING
# =============================================================================
def load_model_and_tokenizer(use_finetuned=True):
    """Load base model và LoRA adapters"""
    print(f"📦 Loading tokenizer: {CFG.base_model_name}")
    tokenizer = AutoTokenizer.from_pretrained(
        CFG.base_model_name,
        trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    print(f"📦 Loading base model...")
    
    # Load base model
    base_model = AutoModelForCausalLM.from_pretrained(
        CFG.base_model_name,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    
    finetuned_model = None
    adapters_info = None
    
    # Load LoRA adapters
    if use_finetuned and os.path.exists(CFG.adapter_path):
        print("📦 Loading fine-tuned adapters...")
        
        def find_adapters(path):
            """Tìm tất cả adapters trong thư mục"""
            found = {}
            if not os.path.exists(path):
                return found
            for root, dirs, files in os.walk(path):
                if "adapter_config.json" in files:
                    for a in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
                        if a in root.lower():
                            found[a] = root
                            break
            return found
        
        adapters_info = find_adapters(CFG.adapter_path)
        
        if adapters_info:
            first = list(adapters_info.keys())[0]
            finetuned_model = PeftModel.from_pretrained(
                base_model,
                adapters_info[first],
                adapter_name=first
            )
            for aid, path in adapters_info.items():
                if aid != first:
                    finetuned_model.load_adapter(path, adapter_name=aid)
            print(f"✅ Loaded {len(adapters_info)} adapters: {list(adapters_info.keys())}")
        else:
            print("⚠️ No adapters found, using base model")
    
    model = finetuned_model if finetuned_model else base_model
    model.eval()
    
    return model, tokenizer, adapters_info


# =============================================================================
# SINGLE AGENT INFERENCE
# =============================================================================
def run_agent(model, tokenizer, agent_id, user_input, adapters=None, max_tokens=None):
    """Chạy một agent để lấy response.

    Fix mode-collapse: fine-tuned dùng sampling + temperature thấp,
    base dùng greedy. Retry 1 lần nếu output rác (nhiều CJK / control chars).
    """

    if max_tokens is None:
        max_tokens = CFG.agent_token_caps.get(agent_id, CFG.agent_max_tokens)

    # Set adapter nếu có
    if adapters and agent_id in adapters and hasattr(model, "set_adapter"):
        model.set_adapter(agent_id)
        use_sampling = True
    else:
        use_sampling = False

    # Build messages
    messages = [
        {"role": "system", "content": AGENT_PROMPTS[agent_id]},
        {"role": "user", "content": user_input},
    ]

    # Tokenize với chat template
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True  # Inference cần True
    )

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    def _generate(rep_penalty):
        kwargs = dict(
            **inputs,
            max_new_tokens=max_tokens,
            repetition_penalty=rep_penalty,
            no_repeat_ngram_size=CFG.no_repeat_ngram_size,
            pad_token_id=tokenizer.pad_token_id,
        )
        if use_sampling:
            kwargs.update(do_sample=True, temperature=CFG.temperature, top_p=CFG.top_p)
        else:
            kwargs.update(do_sample=False)
        with torch.no_grad():
            return model.generate(**kwargs)

    def _is_garbage(text: str) -> bool:
        if not text or len(text.strip()) < 5:
            return True
        non_vn = sum(1 for c in text if 0x2E80 <= ord(c) < 0x3000)  # CJK
        non_vn += sum(1 for c in text if c in "{}[]|\\^~`")
        return non_vn > len(text) * 0.3

    # Generate
    outputs = _generate(CFG.repetition_penalty)

    # Decode
    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True
    ).strip()

    # Retry nếu fine-tuned ra rác
    if use_sampling and _is_garbage(response):
        outputs = _generate(CFG.repetition_penalty * 1.3)
        response = tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        ).strip()

    return response.strip()


# =============================================================================
# EXTRACT ANSWER FROM \boxed{}
# =============================================================================
def extract_boxed(text):
    """Trích xuất đáp án từ \boxed{...}"""
    match = re.search(r'\\boxed\{([^}]+)\}', text)
    if match:
        return match.group(1)
    
    # Fallback: tìm các format khác
    match = re.search(r'đáp án là[:\s]+(.+?)(?:\.|$)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return None


# =============================================================================
# MAIN SOLVER
# =============================================================================
def run_pipeline(model, tokenizer, problem, adapters=None):
    """
    Chạy đầy đủ 5-agent loop trên 1 bài toán, trả về dict ctx.
    Tách ra từ solve_math_vietnamese() để dùng cho compare mode.
    """
    ctx = {}

    # AGENT 1: Chuẩn hóa
    normalized = run_agent(model, tokenizer, "agent1", problem, adapters)
    ctx["agent1"] = normalized

    # AGENT 2: Phân loại (input = bài toán đã chuẩn hóa)
    classification = run_agent(model, tokenizer, "agent2", normalized, adapters)
    ctx["agent2"] = classification

    # AGENT 3: Suy luận
    reasoning_input = f"Bài toán: {normalized}\n\nPhân loại: {classification}"
    reasoning = run_agent(model, tokenizer, "agent3", reasoning_input, adapters)
    ctx["agent3"] = reasoning

    # AGENT 4: Trình bày
    solution_input = f"Bài toán: {normalized}\n\nSuy luận:\n{reasoning}"
    solution = run_agent(model, tokenizer, "agent4", solution_input, adapters)
    ctx["agent4"] = solution

    # AGENT 5: Verify
    verify_input = f"Bài toán: {normalized}\n\nLời giải:\n{solution}"
    verified = run_agent(model, tokenizer, "agent5", verify_input, adapters)
    ctx["agent5"] = verified
    ctx["final_answer"] = extract_boxed(verified)

    return ctx


def print_pipeline(ctx, label):
    """In đẹp output của 1 pipeline với label BASE/FINE-TUNED."""
    icons = {
        "agent1": "🔵 BƯỚC 1 - AGENT 1 (Chuẩn hóa):",
        "agent2": "🟢 BƯỚC 2 - AGENT 2 (Phân loại):",
        "agent3": "🟡 BƯỚC 3 - AGENT 3 (Suy luận):",
        "agent4": "🟠 BƯỚC 4 - AGENT 4 (Trình bày):",
        "agent5": "🔴 BƯỚC 5 - AGENT 5 (Xác nhận):",
    }
    print("\n" + "=" * 70)
    print(f"  📦 PIPELINE: {label}")
    print("=" * 70)
    for aid in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
        print(f"\n{icons[aid]}")
        print(f"{ctx.get(aid, '(empty)')}")
    print(f"\n✅ ĐÁP ÁN CUỐI CÙNG ({label}): \\boxed{{{ctx.get('final_answer')}}}")


def compare_base_vs_finetuned(problem, adapter_path=None):
    """
    Chạy CẢ base + fine-tuned trên cùng 1 bài toán, in song song để so sánh.
    - Base pipeline: model thuần Qwen2.5-Math-1.5B-Instruct, không LoRA.
    - Fine-tuned pipeline: base + LoRA adapters từ adapter_path.
    Lưu log ra archive/logs/compare_<timestamp>.log
    """
    if adapter_path:
        CFG.adapter_path = adapter_path

    print("\n" + "#" * 70)
    print(f"# COMPARE MODE: BASE vs FINE-TUNED")
    print(f"# Problem: {problem}")
    print(f"# Adapter path: {CFG.adapter_path} (exists={os.path.isdir(CFG.adapter_path)})")
    print("#" * 70)

    # Load base (no LoRA)
    print("\n[1/3] Loading BASE model...")
    base_model, base_tok, _ = load_model_and_tokenizer(use_finetuned=False)
    base_ctx = run_pipeline(base_model, base_tok, problem, adapters=None)
    print_pipeline(base_ctx, "BASE Qwen2.5-Math-1.5B (no fine-tuning)")

    # Free memory before loading adapters
    del base_model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # Load fine-tuned (with LoRA)
    ft_ctx = None
    ft_label = "FINE-TUNED"
    if os.path.isdir(CFG.adapter_path):
        # Tìm sub-adapters
        sub = sorted([d for d in Path(CFG.adapter_path).iterdir()
                      if d.is_dir() and d.name.startswith("agent")])
        if sub:
            print(f"\n[2/3] Loading {len(sub)} sub-adapters from {CFG.adapter_path}...")
            print(f"[INFO] Sub-adapters: {[s.name for s in sub]}")
            print("[NOTE] Sub-adapter mode: load each adapter individually (no multi-adapter merge).")
            ft_ctx = {}
            current_model = None
            for sub_dir in sub:
                agent_id = sub_dir.name
                # Need to reload base each time to attach a different adapter
                print(f"\n  Loading {agent_id} from {sub_dir}...")
                if current_model is None:
                    m, t, _ = load_model_and_tokenizer(use_finetuned=False)
                    current_model = m
                    ft_tok = t
                try:
                    ft_model = PeftModel.from_pretrained(current_model, str(sub_dir))
                except Exception as e:
                    print(f"  [WARN] Could not load {agent_id}: {e}")
                    ft_ctx[agent_id] = f"[load failed: {e}]"
                    continue

                cap = CFG.agent_token_caps.get(agent_id, CFG.agent_max_tokens)
                messages = [
                    {"role": "system", "content": AGENT_PROMPTS[agent_id]},
                    {"role": "user", "content": problem},
                ]
                prompt = ft_tok.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True)
                inputs = ft_tok(prompt, return_tensors="pt").to(ft_model.device)
                with torch.no_grad():
                    outputs = ft_model.generate(
                        **inputs,
                        max_new_tokens=cap,
                        do_sample=False,
                        repetition_penalty=CFG.repetition_penalty,
                        no_repeat_ngram_size=CFG.no_repeat_ngram_size,
                        pad_token_id=ft_tok.pad_token_id,
                    )
                response = ft_tok.decode(
                    outputs[0][inputs["input_ids"].shape[1]:],
                    skip_special_tokens=True).strip()
                ft_ctx[agent_id] = response
                # Unload to load next
                try:
                    ft_model = ft_model.unload()
                    current_model = ft_model
                except Exception:
                    current_model = None  # force reload next iter

            # Build synthesized pipeline
            ft_ctx["final_answer"] = extract_boxed(ft_ctx.get("agent5", ""))
            print_pipeline(ft_ctx, ft_label + " (per-agent LoRA)")
        else:
            # Combined adapter case
            print(f"\n[2/3] Loading combined adapter from {CFG.adapter_path}...")
            try:
                ft_model, ft_tok, ft_adapters = load_model_and_tokenizer(use_finetuned=True)
                ft_ctx = run_pipeline(ft_model, ft_tok, problem, adapters=ft_adapters)
                print_pipeline(ft_ctx, ft_label)
            except Exception as e:
                print(f"[ERROR] Failed to load fine-tuned: {e}")
                ft_ctx = None
    else:
        print(f"\n[WARN] Adapter dir does not exist: {CFG.adapter_path}")
        print("Only BASE pipeline evaluated.")

    # Comparison table
    print("\n" + "=" * 70)
    print("  COMPARISON TABLE (first 80 chars per agent)")
    print("=" * 70)
    print(f"{'Agent':<10} | {'BASE':<42} | {'FINETUNED':<42}")
    print("-" * 100)
    for aid in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
        b = base_ctx.get(aid, "")
        f = (ft_ctx or {}).get(aid, "(no adapter)")
        b_short = (b[:40] + "..") if len(b) > 42 else b
        f_short = (f[:40] + "..") if len(f) > 42 else f
        print(f"{aid:<10} | {b_short:<42} | {f_short:<42}")

    # Save log
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path("archive/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"compare_{ts}.log"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Problem: {problem}\nAdapter path: {CFG.adapter_path}\n\n")
        f.write("="*70 + "\nPIPELINE A: BASE MODEL\n" + "="*70 + "\n")
        for k in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
            f.write(f"\n[{k}]\n{base_ctx.get(k, '(none)')}\n")
        f.write(f"\nFinal: {base_ctx.get('final_answer')}\n")
        if ft_ctx:
            f.write("\n" + "="*70 + "\nPIPELINE B: FINE-TUNED\n" + "="*70 + "\n")
            for k in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
                f.write(f"\n[{k}]\n{ft_ctx.get(k, '(none)')}\n")
            f.write(f"\nFinal: {ft_ctx.get('final_answer')}\n")
    print(f"\n💾 Saved compare log: {log_path}")

    return {"base": base_ctx, "finetuned": ft_ctx}


def solve_math_vietnamese(model, tokenizer, problem, adapters=None):
    """
    Giải bài toán tiếng Việt với 5 agent
    
    Flow:
    Agent 1: Chuẩn hóa bài toán
    Agent 2: Phân loại bài toán  
    Agent 3: Suy luận giải toán
    Agent 4: Trình bày lời giải hoàn chỉnh
    Agent 5: Kiểm tra và xác nhận đáp án
    """
    
    print("\n" + "=" * 70)
    print("📝 ĐỀ BÀI")
    print("=" * 70)
    print(f"   {problem}")
    
    ctx = {}
    
    # ─────────────────────────────────────────────────────────
    # AGENT 1: Chuẩn hóa bài toán
    # ─────────────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("🔹 Agent 1: Chuẩn hóa bài toán")
    print("-" * 70)
    normalized = run_agent(model, tokenizer, "agent1", problem, adapters)
    ctx["agent1"] = normalized
    print(f"   {normalized}")
    
    # ─────────────────────────────────────────────────────────
    # AGENT 2: Phân loại bài toán
    # ─────────────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("🔹 Agent 2: Phân loại bài toán")
    print("-" * 70)
    classification = run_agent(model, tokenizer, "agent2", normalized, adapters)
    ctx["agent2"] = classification
    print(f"   {classification}")
    
    # ─────────────────────────────────────────────────────────
    # AGENT 3: Suy luận giải toán
    # ─────────────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("🔹 Agent 3: Suy luận giải toán")
    print("-" * 70)
    reasoning_input = f"Bài toán: {normalized}\n\nPhân loại: {classification}"
    reasoning = run_agent(model, tokenizer, "agent3", reasoning_input, adapters)
    ctx["agent3"] = reasoning
    print(f"   {reasoning}")
    
    # ─────────────────────────────────────────────────────────
    # AGENT 4: Trình bày lời giải hoàn chỉnh
    # ─────────────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("🔹 Agent 4: Trình bày lời giải")
    print("-" * 70)
    solution_input = f"Bài toán: {normalized}\n\nSuy luận:\n{reasoning}"
    solution = run_agent(model, tokenizer, "agent4", solution_input, adapters)
    ctx["agent4"] = solution
    print(f"   {solution}")
    
    # ─────────────────────────────────────────────────────────
    # AGENT 5: Kiểm tra và xác nhận đáp án
    # ─────────────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("🔹 Agent 5: Kiểm tra đáp án")
    print("-" * 70)
    verify_input = f"Bài toán: {normalized}\n\nLời giải:\n{solution}"
    verified = run_agent(model, tokenizer, "agent5", verify_input, adapters)
    ctx["agent5"] = verified
    print(f"   {verified}")
    
    # ─────────────────────────────────────────────────────────
    # Trích xuất đáp án cuối cùng
    # ─────────────────────────────────────────────────────────
    final_answer = extract_boxed(verified)
    
    print("\n" + "=" * 70)
    print("📊 KẾT QUẢ")
    print("=" * 70)
    print(f"   Đáp án cuối cùng: \\boxed{{{final_answer}}}")
    
    return {
        "problem": problem,
        "normalized": normalized,
        "classification": classification,
        "reasoning": reasoning,
        "solution": solution,
        "verified": verified,
        "final_answer": final_answer,
    }


# =============================================================================
# BATCH INFERENCE
# =============================================================================
def solve_batch(model, tokenizer, problems, adapters=None):
    """Giải nhiều bài toán cùng lúc"""
    results = []
    for i, problem in enumerate(problems):
        print(f"\n\n{'#' * 70}")
        print(f"# BÀI {i + 1}/{len(problems)}")
        print(f"{'#' * 70}")
        try:
            result = solve_math_vietnamese(model, tokenizer, problem, adapters)
            results.append(result)
        except Exception as e:
            print(f"❌ Lỗi: {e}")
            results.append({"problem": problem, "error": str(e)})
    return results


# =============================================================================
# SAVE RESULTS
# =============================================================================
def save_results(results, output_path="results.json"):
    """Lưu kết quả ra file"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Đã lưu kết quả vào: {output_path}")


# =============================================================================
# ENTRY POINT
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Vietnamese Math Solver")
    parser.add_argument("--problem", "-p", type=str, help="Bài toán cần giải")
    parser.add_argument("--interactive", "-i", action="store_true", help="Chế độ tương tác")
    parser.add_argument("--batch", "-b", type=str, help="File chứa danh sách bài toán (JSON)")
    parser.add_argument("--output", "-o", type=str, default="results.json", help="File lưu kết quả")
    parser.add_argument("--adapter-path", "-a", type=str, help="Đường dẫn adapters")
    parser.add_argument("--compare", "-c", action="store_true",
                        help="So sánh BASE vs FINE-TUNED trên cùng 1 bài toán")

    args = parser.parse_args()

    # Update adapter path nếu được cung cấp
    if args.adapter_path:
        CFG.adapter_path = args.adapter_path

    # ─────────────────────────────────────────────────────────
    # COMPARE MODE: BASE vs FINE-TUNED (chạy 1 lần cho 1 bài)
    # ─────────────────────────────────────────────────────────
    if args.compare:
        compare_problem = args.problem or (
            "Một hộp có 5 bi đỏ và 3 bi xanh. Lấy ngẫu nhiên 2 bi không hoàn lại. "
            "a) Tính xác suất để cả 2 bi đều đỏ. "
            "b) Nếu biết bi thứ nhất là bi đỏ, tính xác suất bi thứ hai cũng là bi đỏ."
        )
        compare_base_vs_finetuned(compare_problem, adapter_path=CFG.adapter_path)
        return

    # Load model
    print("🚀 Loading model...")
    model, tokenizer, adapters = load_model_and_tokenizer(CFG.use_finetuned)
    
    if args.interactive:
        # Chế độ tương tác
        print("\n" + "=" * 70)
        print("🎯 VIETNAMESE MATH SOLVER - CHẾ ĐỘ TƯƠNG TÁC")
        print("=" * 70)
        print("Nhập bài toán tiếng Việt để giải (gõ 'exit' để thoát)")
        print("-" * 70)
        
        while True:
            print("\n> ", end="")
            problem = input().strip()
            
            if problem.lower() in ["exit", "quit", "q"]:
                break
            
            if not problem:
                continue
            
            solve_math_vietnamese(model, tokenizer, problem, adapters)
    
    elif args.batch:
        # Chế độ batch
        with open(args.batch, "r", encoding="utf-8") as f:
            problems = json.load(f)
        
        results = solve_batch(model, tokenizer, problems, adapters)
        save_results(results, args.output)
    
    elif args.problem:
        # Giải một bài toán
        result = solve_math_vietnamese(model, tokenizer, args.problem, adapters)
        save_results([result], args.output)
    
    else:
        # Demo
        print("\n" + "=" * 70)
        print("🎯 VIETNAMESE MATH SOLVER - DEMO")
        print("=" * 70)

        demo_problems = [
            "Một người có 50 quả táo. Bán đi 3/5 số táo. Hỏi còn lại bao nhiêu quả?",
            "Tính diện tích hình tròn có bán kính 7cm (lấy π ≈ 3.14).",
            "Một chiếc xe đi từ A đến B với vận tốc 60km/h trong 2.5 giờ. Tính quãng đường AB.",
            "Một hộp có 5 bi đỏ và 3 bi xanh. Lấy ngẫu nhiên 2 bi không hoàn lại. "
            "Tính xác suất để cả 2 bi đều đỏ.",
        ]

        results = solve_batch(model, tokenizer, demo_problems, adapters)
        save_results(results, args.output)


if __name__ == "__main__":
    main()
