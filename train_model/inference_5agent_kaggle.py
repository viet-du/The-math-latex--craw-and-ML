"""
5-Agent Math Solver - Inference Script
- Base model và Fine-tuned model
- Hiển thị: Bước giải + Đáp án
- Che dấu suy nghĩ nội bộ của agent
"""

import subprocess, sys, os, re, gc, time, json
import torch
import numpy as np
from IPython.display import display, HTML, Latex, clear_output

# ══════════════════════════════════════════════════════════════
# CELL 1: Install dependencies
# ══════════════════════════════════════════════════════════════
def setup_environment():
    print("⚙️  Setting up environment...")
    
    # Uninstall conflicting packages
    for pkg in ["torchao"]:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "uninstall", "-y", pkg],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except:
            pass
    
    # Install required packages
    packages = [
        "transformers>=4.45.0",
        "peft>=0.13.0",
        "accelerate",
        "bitsandbytes>=0.46.1",
    ]
    
    for pkg in packages:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-q", pkg
        ], stdout=subprocess.DEVNULL)
    
    print("✅ Environment ready")

setup_environment()

# ══════════════════════════════════════════════════════════════
# CELL 2: Imports
# ══════════════════════════════════════════════════════════════
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
from IPython.display import display, HTML, Latex

# ══════════════════════════════════════════════════════════════
# CELL 3: Configuration
# ══════════════════════════════════════════════════════════════
class CFG:
    # Base model
    base_model_name = "Qwen/Qwen2.5-Math-1.5B-Instruct"
    
    # Fine-tuned adapters (thay đổi theo đường dẫn của bạn)
    adapter_path = "/kaggle/input/datasets/vitduq/train-modle317/outputs"
    
# Generation settings
    max_new_tokens = 256
    temperature = 0.3  # Lower = more deterministic, less repetition
    top_p = 0.85

    # Mode: "base" hoặc "finetuned"
    use_finetuned = True

    # Compare mode: chạy song song BASE vs FINE-TUNED trên cùng 1 bài
    compare_mode = True  # ← Set True để so sánh, False để chạy single pipeline

    # Bài toán mặc định cho compare mode (xác suất thống kê)
    compare_problem = (
        "Một hộp có 5 bi đỏ và 3 bi xanh. Lấy ngẫu nhiên 2 bi không hoàn lại. "
        "a) Tính xác suất để cả 2 bi đều đỏ. "
        "b) Nếu biết bi thứ nhất là bi đỏ, tính xác suất bi thứ hai cũng là bi đỏ."
    )

    # Quantization (set False nếu bitsandbytes lỗi)
    use_quantization = False

    # Max tokens per agent (tăng lên để có đủ nội dung)
    agent_max_tokens = 384

    # Repetition control (Fix: agent4 lặp 13 dòng, agent5 lặp 12 derivatives)
    repetition_penalty = 1.5
    no_repeat_ngram_size = 6

    # Per-agent token caps (tăng từ 32-192 → 128-512 để tránh mode-collapse
    # tiếng Việt khi adapter chưa converge mạnh)
    agent_token_caps = {
        "agent1": 256,   # chuẩn hóa đề (đủ để viết lại đề bài tiếng Việt)
        "agent2": 96,    # phân loại dạng toán
        "agent3": 512,   # suy luận — quan trọng nhất, cần nhiều token
        "agent4": 384,   # trình bày lời giải LaTeX
        "agent5": 192,   # verify ngắn
    }

print(f"CFG: base_model={CFG.base_model_name}")
print(f"CFG: use_finetuned={CFG.use_finetuned}")

# ══════════════════════════════════════════════════════════════
# CELL 4: System Prompts (ẩn với người dùng)
# ⚠️ FIX F: These prompts must match the training data EXACTLY. The
# training script (qwen25_math_5agent_lora_kaggle.py, after Fix B)
# reads from DATA/5agent_final/, whose system prompts come from
# scripts/transform_for_5agent.py (SYSTEM_PROMPTS dict). Mismatched
# prompts inflate eval loss because the model sees a different
# system message at inference than the one it was trained on. If
# you ever swap the training data dir back to 5agent_expanded
# (which uses scripts/expand_dataset.py prompts) you must also
# update this dict -- see docs/working_rule.md.
# ══════════════════════════════════════════════════════════════
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
        "- Chủ đề: Phân số, Hình học, Đại số, Tỉ lệ, Phần trăm, Đạo hàm, Xác suất\n"
        "- Loại: Tính toán, Chứng minh, Ứng dụng\n"
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

# ══════════════════════════════════════════════════════════════
# CELL 5: Load Model
# ══════════════════════════════════════════════════════════════
def load_model_and_tokenizer(use_finetuned=True):
    print("📦 Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        CFG.base_model_name,
        trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    print("📦 Loading base model...")
    
    # Load model - có hoặc không quantization
    if CFG.use_quantization:
        try:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
            base_model = AutoModelForCausalLM.from_pretrained(
                CFG.base_model_name,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True,
                quantization_config=bnb_config,
            )
            print("   [OK] Using 4-bit quantization (bitsandbytes)")
        except Exception as e:
            print(f"   [WARN] bitsandbytes failed ({e}), loading without quantization")
            base_model = AutoModelForCausalLM.from_pretrained(
                CFG.base_model_name,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True,
            )
    else:
        base_model = AutoModelForCausalLM.from_pretrained(
            CFG.base_model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
    
    # ─── BASE MODEL (shared) ──────────────────────────────────────
    # Adapter của mỗi agent được load riêng bên trong run_agent_internal()
    # để tránh stacked-LoRA interference gây garbage output.
    model = base_model
    model.eval()

    # adapters_info: {agent_id -> checkpoint_path}
    adapters_info = None

    if use_finetuned and os.path.exists(CFG.adapter_path):
        print("📦 Scanning for fine-tuned adapter checkpoints...")

        def find_adapters(path):
            """Trả về dict {agent_id: [list of checkpoint paths]}."""
            found = {}
            if not os.path.exists(path):
                return found
            for root, dirs, files in os.walk(path):
                if "adapter_config.json" in files:
                    for a in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
                        if a in root.lower():
                            found.setdefault(a, []).append(root)
                            break
            # Sort mỗi agent: ưu tiên "final" trước, rồi checkpoint số cao nhất
            def _sort_key(p):
                base = os.path.basename(p.rstrip("/"))
                if base == "final":
                    return (0, 0)
                # checkpoint-N → N
                try:
                    n = int(base.split("-")[-1])
                    return (1, -n)
                except Exception:
                    return (2, 0)
            for a in found:
                found[a].sort(key=_sort_key)
            return found

        adapters_info = find_adapters(CFG.adapter_path)

        if adapters_info:
            total_ckpts = sum(len(v) for v in adapters_info.values())
            print(f"✅ Found {total_ckpts} adapter checkpoints across "
                  f"{len(adapters_info)} agents:")
            for aid, paths in sorted(adapters_info.items()):
                print(f"   {aid}: {len(paths)} checkpoint(s)")
                for p in paths:
                    print(f"      • {p}")
        else:
            print("⚠️  No adapter checkpoints found — falling back to base model.")

    return model, tokenizer, adapters_info


# ══════════════════════════════════════════════════════════════
# CELL 5.5: EDA — Auto-pick BEST checkpoint mỗi agent
# ══════════════════════════════════════════════════════════════
# Scan tất cả checkpoints của mỗi agent, generate thử 1 bài mẫu,
# score theo độ "sạch" (ít CJK noise, có công thức toán, dừng đúng lúc),
# rồi ghi đè adapters_info để main pipeline chỉ dùng checkpoint tốt nhất.

_EDA_PROBES = {
    # probe ngắn, cố ý khác đề inference chính để test generalization
    "agent1": "Hộp có 4 viên bi trắng, 6 viên bi đen. Lấy ngẫu nhiên 2 viên không hoàn lại.",
    "agent2": "Hộp có 4 viên bi trắng, 6 viên bi đen. Lấy ngẫu nhiên 2 viên không hoàn lại.",
    "agent3": "Hộp có 4 viên bi trắng, 6 viên bi đen. Lấy ngẫu nhiên 2 viên không hoàn lại. Tính xác suất cả 2 viên đều trắng.",
    "agent4": "Tính $\\binom{5}{2}$.",
    "agent5": "Tính $\\binom{5}{2}$ và $\\frac{5}{8} \\cdot \\frac{4}{7}$.",
}


def _score_checkpoint_output(text: str) -> float:
    """
    Score càng cao = output càng "sạch" và có nội dung toán.
    Penalty: CJK noise, ký tự đặc biệt vô nghĩa.
    Bonus: có số, có \\frac/\\binom/$, có từ khoá tiếng Việt.
    """
    if not text or len(text.strip()) < 5:
        return -1000.0
    n = len(text)

    # Penalty: CJK chars (model bị degenerate khi output CJK không chủ đích)
    cjk = sum(1 for c in text if 0x2E80 < ord(c) < 0x3000
              or 0x3400 < ord(c) < 0x4DBF
              or 0x4E00 < ord(c) < 0x9FFF)
    # Penalty: emoji
    emoji = sum(1 for c in text if ord(c) > 0x1F000)
    # Penalty: chuỗi rất dài mà không có dấu chấm/khoảng trắng = repetitive
    no_space = len(text.replace(" ", "").replace("\n", ""))
    space_ratio = (n - no_space) / max(n, 1)
    # Bonus: có LaTeX math
    has_frac = text.count("\\frac")
    has_binom = text.count("\\binom")
    has_dollar = text.count("$") + text.count("\\(")
    # Bonus: có số
    has_digit = sum(1 for c in text if c.isdigit())
    # Bonus: tiếng Việt có dấu
    vn_chars = sum(1 for c in text if c in "ăâđêôơưĂÂĐÊÔƠƯáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỳ")

    score = (
        + len(text) * 0.1          # khuyến khích output đủ dài
        + cjk * -2.0               # phạt mạnh CJK
        + emoji * -3.0             # phạt emoji
        + space_ratio * 50         # khuyến khích có cấu trúc
        + has_frac * 8
        + has_binom * 8
        + has_dollar * 3
        + min(has_digit, 20) * 1.0
        + min(vn_chars, 20) * 2.0
    )
    return score


def auto_pick_best_checkpoints(model, tokenizer, adapters_info,
                               verbose=True):
    """
    Với mỗi agent có ≥2 checkpoints, probe từng cái rồi chọn cái score cao nhất.
    Trả về dict {agent_id: best_ckpt_path} (đã được lọc).
    """
    if not adapters_info:
        return {}

    best_per_agent = {}
    import torch

    # Đếm số agent có nhiều hơn 1 checkpoint → cần scan
    multi_ckpt_agents = [a for a, paths in adapters_info.items()
                         if len(paths) > 1]
    if not multi_ckpt_agents:
        # Mỗi agent chỉ có 1 ckpt → dùng luôn
        for a, paths in adapters_info.items():
            best_per_agent[a] = paths[0]
        if verbose:
            print("\n🔍 EDA: mỗi agent chỉ có 1 checkpoint → skip scan.")
        return best_per_agent

    if verbose:
        print(f"\n🔍 EDA: scanning {sum(len(adapters_info[a]) for a in multi_ckpt_agents)} "
              f"checkpoints across {len(multi_ckpt_agents)} agents...")
        print(f"   (candidates: {', '.join(multi_ckpt_agents)})")
        print(f"   ⏱️  Ước tính: ~{sum(len(adapters_info[a]) for a in multi_ckpt_agents) * 8}s\n")

    # Save trạng thái adapter hiện tại (nếu có) để restore
    original_active = getattr(model, "active_adapter", None)

    results = {}  # {agent_id: [(path, score, sample_text), ...]}

    for agent_id in multi_ckpt_agents:
        if verbose:
            print(f"\n{'─' * 60}")
            print(f"  📂 Agent: {agent_id}  ({len(adapters_info[agent_id])} checkpoints)")
            print(f"{'─' * 60}")

        probe_input = _EDA_PROBES.get(agent_id, _EDA_PROBES["agent3"])
        messages = [
            {"role": "system", "content": AGENT_PROMPTS[agent_id]},
            {"role": "user", "content": probe_input},
        ]
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        results[agent_id] = []
        for ckpt_path in adapters_info[agent_id]:
            try:
                # Load adapter này
                test_name = f"_eda_{agent_id}_{os.path.basename(ckpt_path)}"
                model.load_adapter(ckpt_path, adapter_name=test_name)
                model.set_adapter(test_name)
                # Đảm bảo trên GPU
                model.to(next(model.parameters()).device)

                # Generate greedy (ổn định nhất cho EDA)
                eos_ids = [151643, 151645]
                with torch.no_grad():
                    out = model.generate(
                        **inputs,
                        max_new_tokens=CFG.agent_token_caps.get(
                            agent_id, CFG.agent_max_tokens),
                        repetition_penalty=CFG.repetition_penalty,
                        no_repeat_ngram_size=CFG.no_repeat_ngram_size,
                        pad_token_id=tokenizer.pad_token_id,
                        eos_token_id=eos_ids,
                        do_sample=False,
                    )
                text = tokenizer.decode(
                    out[0][inputs["input_ids"].shape[1]:],
                    skip_special_tokens=True).strip()

                # Cleanup adapter để load tiếp
                model.delete_adapter(test_name)

                score = _score_checkpoint_output(text)
                results[agent_id].append((ckpt_path, score, text))

                # Preview
                preview = text.replace("\n", " ")[:80]
                ckpt_name = os.path.basename(ckpt_path.rstrip("/"))
                if verbose:
                    flag = ""
                    if score < 0:
                        flag = "  ⚠️  garbage"
                    print(f"   {ckpt_name:<20} score={score:+7.1f}  "
                          f"'{preview}...'{flag}")

            except Exception as e:
                if verbose:
                    print(f"   {os.path.basename(ckpt_path)}: ERROR {e}")
                results[agent_id].append((ckpt_path, -9999.0, ""))

        # Chọn best (score cao nhất, fallback: path đầu tiên)
        if results[agent_id]:
            results[agent_id].sort(key=lambda x: x[1], reverse=True)
            best_per_agent[agent_id] = results[agent_id][0][0]
            best_name = os.path.basename(best_per_agent[agent_id].rstrip("/"))
            best_score = results[agent_id][0][1]
            if verbose:
                print(f"   → BEST: {best_name} (score={best_score:+.1f})")

    # Agents chỉ có 1 ckpt: giữ nguyên
    for a, paths in adapters_info.items():
        if a not in best_per_agent:
            best_per_agent[a] = paths[0]

    # Restore adapter gốc
    if original_active:
        try:
            model.set_adapter(original_active)
        except Exception:
            pass

    if verbose:
        print(f"\n{'═' * 60}")
        print(f"  ✅ AUTO-PICK COMPLETE — adapter map:")
        print(f"{'═' * 60}")
        for a in sorted(best_per_agent):
            orig = adapters_info[a][0]
            chosen = best_per_agent[a]
            tag = "" if orig == chosen else "  (≠ default)"
            print(f"   {a}: {os.path.basename(chosen.rstrip('/'))}{tag}")
        print()

    return best_per_agent

# ══════════════════════════════════════════════════════════════
# CELL 6: Run Single Agent (nội bộ, không hiển thị)
# ══════════════════════════════════════════════════════════════
def run_agent_internal(model, tokenizer, agent_id, user_input, adapters=None, max_tokens=None):
    """
    Chạy agent nội bộ - không hiển thị suy nghĩ.

    Mỗi agent dùng adapter RIÊNG của nó (load → generate → unload).
    KHÔNG stack 5 adapters cùng lúc để tránh interference gây garbage.
    """

    if max_tokens is None:
        max_tokens = CFG.agent_token_caps.get(agent_id, CFG.agent_max_tokens)

    # ── Determine generation mode ────────────────────────────────
    adapter_path = None
    if adapters and agent_id in adapters:
        adapter_path = adapters[agent_id]
        use_sampling = True   # fine-tuned: sampling + temperature
    else:
        use_sampling = False  # base: greedy deterministic

    # ── Build prompt ─────────────────────────────────────────────
    messages = [
        {"role": "system", "content": AGENT_PROMPTS[agent_id]},
        {"role": "user", "content": user_input},
    ]
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    # DEBUG (1 lần): in token info để verify chat template match training
    if adapter_path and not getattr(run_agent_internal, "_debug_printed", False):
        run_agent_internal._debug_printed = True
        print(f"\n   🔍 [DEBUG] adapter={agent_id}")
        print(f"      eos_token_id={tokenizer.eos_token_id} "
              f"('{tokenizer.eos_token}')")
        print(f"      pad_token_id={tokenizer.pad_token_id}")
        print(f"      im_end id={tokenizer.convert_tokens_to_ids('<|im_end|>')}")
        print(f"      prompt length={inputs['input_ids'].shape[1]} tokens")
        print(f"      prompt tail (last 200 chars):")
        print(f"      ...{prompt[-200:]!r}\n")

    # ── Generate ──────────────────────────────────────────────────
    def _generate(work_model, do_sample):
        # Qwen2.5-Math-Instruct dùng 2 token để kết thúc:
        #   <|endoftext|> = 151643 (base EOS / pretrain)
        #   <|im_end|>    = 151645 (chat template, sinh ra bởi apply_chat_template)
        # Hard-code cả 2 để chắc chắn không phụ thuộc tokenizer.eos_token_id
        # (vì một số bản merge tokenizer trả về None khi convert single token).
        eos_ids = [151643, 151645]

        gen_kwargs = dict(
            **inputs,
            max_new_tokens=max_tokens,
            repetition_penalty=CFG.repetition_penalty,
            no_repeat_ngram_size=CFG.no_repeat_ngram_size,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=eos_ids,           # ← FIX: dừng đúng lúc
        )
        if do_sample:
            gen_kwargs.update(
                do_sample=True,
                temperature=CFG.temperature,
                top_p=CFG.top_p,
            )
        else:
            gen_kwargs["do_sample"] = False
        with torch.no_grad():
            return work_model.generate(**gen_kwargs)

    def _is_garbage(text: str) -> bool:
        """>30% noise/CJK chars → retry."""
        if not text or len(text.strip()) < 5:
            return True
        noise = sum(1 for c in text
                    if (0x2E80 < ord(c) < 0x3000)   # CJK blocks
                    or c in "{}[]|\\^~`")
        return noise > len(text) * 0.3

    # ── Load adapter + generate ──────────────────────────────────
    active_adapter = None
    try:
        if adapter_path:
            # Load adapter riêng lên base model (base model KHÔNG bị ảnh hưởng
            # bởi adapters khác vì ta không stack ở đây)
            active_adapter = f"tmp_{agent_id}"
            model.load_adapter(adapter_path, adapter_name=active_adapter)
            model.set_adapter(active_adapter)

            # CRITICAL: peft load_adapter không tự move LoRA weights sang device
            # → ép toàn bộ model (cả base + LoRA params) sang GPU
            device = next(model.parameters()).device
            model.to(device)

            print(f"   [{agent_id}] loaded adapter: {adapter_path}")

        outputs = _generate(model, use_sampling)
        response = tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        ).strip()

        # Nếu garbage (CJK noise) → retry với greedy (no sampling).
        # Sampling với temp=0.3 + tokenizer degenerate dễ rơi vào noise.
        # Greedy thường cho output ổn định hơn.
        if use_sampling and _is_garbage(response):
            print(f"   [{agent_id}] sampling garbage → retry greedy")
            outputs = _generate(model, False)
            response = tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=True,
            ).strip()

        # Nếu vẫn garbage lần 2 → fallback: disable adapter để dùng base
        if _is_garbage(response):
            print(f"   [{agent_id}] still garbage → fallback BASE (no adapter)")
            if active_adapter and hasattr(model, "disable_adapter"):
                model.disable_adapter()
            outputs = _generate(model, False)
            response = tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=True,
            ).strip()

    finally:
        # ── UNLOAD + DELETE adapter thật ─────────────────────────
        # disable_adapter() không xóa khỏi peft_config, chỉ tắt tạm.
        # → Sau 5 lần agent, dict có 5 adapter cũ → memory leak + device bug.
        # Phải delete_adapter() để giải phóng hoàn toàn.
        if active_adapter and hasattr(model, "delete_adapter"):
            try:
                model.delete_adapter(active_adapter)
            except Exception:
                # Fallback: ít nhất disable
                if hasattr(model, "disable_adapter"):
                    model.disable_adapter()

    return response.strip()

# ══════════════════════════════════════════════════════════════
# CELL 7: Solve Math Problem
# ══════════════════════════════════════════════════════════════
def solve_math_problem(model, tokenizer, problem, adapters=None):
    """
    Giải bài toán với 5 agent
    Chỉ hiển thị: Bước giải + Đáp án cuối cùng
    """
    
    print("\n" + "═" * 70)
    print("📝 ĐỀ BÀI")
    print("═" * 70)
    print(f"   {problem}")
    
    ctx = {}
    steps_display = []
    
    # ─────────────────────────────────────────────────────────
    # AGENT 1: Chuẩn hóa
    # ─────────────────────────────────────────────────────────
    step1 = run_agent_internal(model, tokenizer, "agent1", problem, adapters)
    ctx["agent1"] = step1
    steps_display.append(("Bước 1: Chuẩn hóa", step1))
    
    # ─────────────────────────────────────────────────────────
    # AGENT 2: Phân loại
    # ─────────────────────────────────────────────────────────
    step2 = run_agent_internal(model, tokenizer, "agent2", step1, adapters)
    ctx["agent2"] = step2
    steps_display.append(("Bước 2: Phân loại", step2))
    
    # ─────────────────────────────────────────────────────────
    # AGENT 3: Suy luận
    # ─────────────────────────────────────────────────────────
    history = f"Đề bài: {problem}\n\nChuẩn hóa: {step1}\n\nPhân loại: {step2}"
    step3 = run_agent_internal(model, tokenizer, "agent3", history, adapters)
    ctx["agent3"] = step3
    steps_display.append(("Bước 3: Suy luận", step3))
    
    # ─────────────────────────────────────────────────────────
    # AGENT 4: Trình bày lời giải
    # ─────────────────────────────────────────────────────────
    solution_input = f"Đề: {problem}\n\nSuy luận:\n{step3}"
    step4 = run_agent_internal(model, tokenizer, "agent4", solution_input, adapters)
    ctx["agent4"] = step4
    steps_display.append(("Bước 4: Lời giải", step4))
    
    # ─────────────────────────────────────────────────────────
    # AGENT 5: Xác minh
    # ─────────────────────────────────────────────────────────
    verify_input = f"Lời giải:\n{step4}"
    step5 = run_agent_internal(model, tokenizer, "agent5", verify_input, adapters)
    ctx["agent5"] = step5
    steps_display.append(("Bước 5: Xác minh", step5))
    
    # ═════════════════════════════════════════════════════════
    # TRÍCH ĐÁP ÁN
    # ═════════════════════════════════════════════════════════
    final_answer = extract_answer(step4) or extract_answer(step5) or extract_answer(step3)
    
    return steps_display, final_answer, ctx

def extract_answer(text):
    """Trích xuất đáp án từ \\boxed{...}"""
    if not text:
        return None
    matches = re.findall(r'\\boxed\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', text)
    return matches[-1].strip() if matches else None

# ══════════════════════════════════════════════════════════════
# CELL 8: Display Results - Beautiful Format
# ══════════════════════════════════════════════════════════════
def display_solution_beautiful(steps_display, final_answer, problem):
    """Hiển thị lời giải đẹp mắt"""
    
    clear_output(wait=True)
    
    # Header
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "LỜI GIẢI CHI TIẾT" + " " * 27 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    # Problem
    print("📝 ĐỀ BÀI:")
    print(f"   {problem}")
    print()
    
    # Steps
    step_colors = ['🔵', '🟢', '🟡', '🟠', '🟣']
    
    for i, (title, content) in enumerate(steps_display):
        print("─" * 70)
        print(f" {step_colors[i]} {title.upper()}")
        print("─" * 70)
        
        # Clean and format content
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line:
                print(f"   {line}")
        print()
    
    # Final Answer
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 25 + "✨ ĐÁP ÁN ✨" + " " * 26 + "║")
    print("╚" + "═" * 68 + "╝")
    
    if final_answer:
        print()
        print("   ┌────────────────────────────────────────────┐")
        print("   │                                            │")
        print(f"   │            \\boxed{{{final_answer}}}               │")
        print("   │                                            │")
        print("   └────────────────────────────────────────────┘")
    else:
        print("   ⚠️ Không tìm được đáp án cuối cùng")
    
    print()

def display_html_solution(steps_display, final_answer, problem):
    """Hiển thị dạng HTML đẹp trong notebook"""
    
    colors = {
        0: '#3498db',  # Blue
        1: '#2ecc71',  # Green
        2: '#f39c12',  # Orange
        3: '#e74c3c',  # Red
        4: '#9b59b6',  # Purple
    }
    
    step_names = ['CHUẨN HÓA', 'PHÂN LOẠI', 'SUY LUẬN', 'LỜI GIẢI', 'XÁC MINH']
    
    html = f"""
    <div style='font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto;'>
    
    <!-- Header -->
    <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 15px; margin-bottom: 20px;'>
        <h1 style='margin: 0;'>🔢 LỜI GIẢI CHI TIẾT</h1>
    </div>
    
    <!-- Problem -->
    <div style='background: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #3498db;'>
        <h3 style='color: #3498db; margin-top: 0;'>📝 ĐỀ BÀI</h3>
        <p style='font-size: 18px; margin: 10px 0;'>{problem}</p>
    </div>
    """
    
    for i, (title, content) in enumerate(steps_display):
        color = colors[i]
        name = step_names[i]
        
        # Extract math for LaTeX display
        math_blocks = []
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Find LaTeX blocks
            display_math = re.findall(r'\$\$([^$]+)\$\$', line)
            inline_math = re.findall(r'\$([^$]+)\$', line)
            boxed = re.search(r'\\boxed\{([^}]+)\}', line)
            
            if display_math:
                for m in display_math:
                    math_blocks.append(f"$${m}$$")
            elif boxed:
                math_blocks.append(f"$$\\boxed{{{boxed.group(1)}}}$$")
            elif inline_math:
                for m in inline_math:
                    math_blocks.append(f"${m}$")
            else:
                math_blocks.append(line)
        
        html += f"""
        <div style='background: white; padding: 20px; border-radius: 10px; margin-bottom: 15px; border-left: 5px solid {color}; box-shadow: 0 2px 5px rgba(0,0,0,0.1);'>
            <h3 style='color: {color}; margin-top: 0;'>🔹 {name}</h3>
        """
        
        for block in math_blocks:
            if block.startswith('$') and ('\\' in block or len(block) > 2):
                html += f"<div style='font-size: 18px; margin: 10px 0; padding: 10px; background: #f0f0f0; border-radius: 5px; text-align: center;'>{block}</div>"
            else:
                html += f"<p style='margin: 8px 0;'>{block}</p>"
        
        html += "</div>"
    
    # Final Answer
    if final_answer:
        html += f"""
        <div style='background: linear-gradient(135deg, #00d9ff 0%, #00b4d8 100%); padding: 30px; border-radius: 15px; text-align: center; margin-top: 20px;'>
            <h2 style='color: white; margin: 0;'>✨ ĐÁP ÁN CUỐI CÙNG ✨</h2>
            <div style='background: white; padding: 20px; border-radius: 10px; margin-top: 20px; font-size: 24px;'>
                $$\\boxed{{\\displaystyle {final_answer}}}$$
            </div>
        </div>
        """
    else:
        html += """
        <div style='background: #fff3cd; padding: 20px; border-radius: 10px; text-align: center; margin-top: 20px; border: 2px solid #ffc107;'>
            <h3 style='color: #856404; margin: 0;'>⚠️ Không tìm được đáp án</h3>
        </div>
        """
    
    html += "</div>"
    
    display(HTML(html))

# ══════════════════════════════════════════════════════════════
# CELL 10: Evaluation Metrics
# ══════════════════════════════════════════════════════════════
class MathEvaluator:
    """Đánh giá chất lượng giải toán"""
    
    def __init__(self):
        self.results = []
    
    @staticmethod
    def normalize_answer(ans):
        """Chuẩn hóa đáp án để so sánh"""
        if ans is None:
            return None
        
        ans = str(ans).strip()
        # Remove latex commands
        ans = re.sub(r'\\boxed\{|\}', '', ans)
        ans = re.sub(r'\\displaystyle', '', ans)
        ans = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'(\1)/(\2)', ans)
        ans = re.sub(r'\\sqrt\{([^{}]+)\}', r'sqrt(\1)', ans)
        ans = re.sub(r'\\cdot|\\times', '*', ans)
        ans = re.sub(r'\\div|/', '/', ans)
        ans = re.sub(r'\\\w+', '', ans)  # remove other commands
        ans = re.sub(r'[{}]', '', ans)
        ans = re.sub(r'\s+', '', ans)
        ans = ans.replace(' ', '')
        
        return ans
    
    def exact_match(self, predicted, ground_truth):
        """Exact match score"""
        pred_norm = self.normalize_answer(predicted)
        truth_norm = self.normalize_answer(ground_truth)
        
        if pred_norm is None or truth_norm is None:
            return 0.0
        
        return 1.0 if pred_norm == truth_norm else 0.0
    
    def numerical_match(self, predicted, ground_truth, tolerance=1e-4):
        """Numerical match (cho đáp án số)"""
        pred_norm = self.normalize_answer(predicted)
        truth_norm = self.normalize_answer(ground_truth)
        
        if pred_norm is None or truth_norm is None:
            return 0.0
        
        # Try to extract numbers
        try:
            pred_num = float(re.search(r'-?\d+\.?\d*', pred_norm).group())
            truth_num = float(re.search(r'-?\d+\.?\d*', truth_norm).group())
            
            if abs(truth_num) < tolerance:
                return 1.0 if abs(pred_num) < tolerance else 0.0
            
            return 1.0 if abs(pred_num - truth_num) / abs(truth_num) < tolerance else 0.0
        except:
            return 0.0
    
    def latex_validity(self, solution_text):
        """Check LaTeX validity"""
        if not solution_text:
            return 0.0
        
        score = 0.0
        # Has boxed answer
        if '\\boxed{' in solution_text:
            score += 0.4
        # Has math notation
        if '$' in solution_text or '\\' in solution_text:
            score += 0.3
        # Has step-by-step structure
        if re.search(r'(Bước|Step|Step|Buoc)\s*\d+', solution_text):
            score += 0.3
        
        return score
    
    def vietnamese_quality(self, solution_text):
        """Check Vietnamese quality"""
        if not solution_text:
            return 0.0
        
        letters = [c for c in solution_text if c.isalpha()]
        if not letters:
            return 0.0
        
        vn_ratio = sum(1 for c in letters if ord(c) > 127) / len(letters)
        return min(1.0, vn_ratio * 2)  # score 1.0 if >=50% Vietnamese
    
    def evaluate(self, problem, predicted_answer, solution_text, ground_truth=None, time_taken=0):
        """Đánh giá 1 bài toán"""
        
        result = {
            'problem': problem[:100] + '...' if len(problem) > 100 else problem,
            'predicted': predicted_answer,
            'ground_truth': ground_truth,
            'has_answer': predicted_answer is not None,
            'latex_score': self.latex_validity(solution_text),
            'vn_score': self.vietnamese_quality(solution_text),
            'time_sec': time_taken,
        }
        
        if ground_truth:
            result['exact_match'] = self.exact_match(predicted_answer, ground_truth)
            result['numerical_match'] = self.numerical_match(predicted_answer, ground_truth)
        
        self.results.append(result)
        return result
    
    def summary(self):
        """Tổng kết đánh giá"""
        if not self.results:
            return "Chưa có kết quả đánh giá"
        
        n = len(self.results)
        has_answer_count = sum(1 for r in self.results if r['has_answer'])
        avg_latex = np.mean([r['latex_score'] for r in self.results])
        avg_vn = np.mean([r['vn_score'] for r in self.results])
        avg_time = np.mean([r['time_sec'] for r in self.results])
        
        summary = {
            'total': n,
            'has_answer': has_answer_count,
            'answer_rate': has_answer_count / n * 100,
            'avg_latex_score': avg_latex,
            'avg_vn_score': avg_vn,
            'avg_time_sec': avg_time,
        }
        
        # Add accuracy if ground truth available
        if 'exact_match' in self.results[0]:
            em = np.mean([r['exact_match'] for r in self.results])
            nm = np.mean([r['numerical_match'] for r in self.results])
            summary['exact_match'] = em * 100
            summary['numerical_match'] = nm * 100
        
        return summary
    
    def print_report(self):
        """In báo cáo đánh giá"""
        s = self.summary()
        
        print("\n" + "═" * 70)
        print("📊 BÁO CÁO ĐÁNH GIÁ")
        print("═" * 70)
        print(f"   Tổng số bài:        {s['total']}")
        print(f"   Có đáp án:          {s['has_answer']} ({s['answer_rate']:.1f}%)")
        print(f"   LaTeX quality:      {s['avg_latex_score']:.3f}/1.0")
        print(f"   Tiếng Việt:         {s['avg_vn_score']:.3f}/1.0")
        print(f"   Thời gian TB:       {s['avg_time_sec']:.2f}s")
        
        if 'exact_match' in s:
            print(f"   Exact Match:        {s['exact_match']:.2f}%")
            print(f"   Numerical Match:    {s['numerical_match']:.2f}%")
        
        print("═" * 70)
    
    def save_to_csv(self, filepath):
        """Lưu kết quả ra CSV"""
        import pandas as pd
        df = pd.DataFrame(self.results)
        df.to_csv(filepath, index=False, encoding='utf-8')
        print(f"💾 Saved: {filepath}")

# ══════════════════════════════════════════════════════════════
# CELL 11: Compare Base vs Fine-tuned
# ══════════════════════════════════════════════════════════════
def compare_models(eval_data, ground_truths=None):
    """So sánh base model và fine-tuned model"""
    
    print("\n" + "═" * 70)
    print("⚖️  SO SÁNH BASE vs FINE-TUNED")
    print("═" * 70)
    
    results = {}
    
    for mode_name, use_ft in [("BASE", False), ("FINE-TUNED", True)]:
        print(f"\n🔄 Testing {mode_name}...")
        
        # Load model
        torch.cuda.empty_cache()
        gc.collect()
        model, tokenizer, adapters = load_model_and_tokenizer(use_finetuned=use_ft)
        
        evaluator = MathEvaluator()
        
        for i, problem in enumerate(eval_data):
            ground_truth = ground_truths[i] if ground_truths else None
            
            start_time = time.time()
            steps_display, final_answer, ctx = solve_math_problem(
                model, tokenizer, problem, adapters
            )
            elapsed = time.time() - start_time
            
            solution_text = "\n".join([c for _, c in steps_display])
            
            result = evaluator.evaluate(
                problem, final_answer, solution_text, ground_truth, elapsed
            )
            
            print(f"   [{i+1}/{len(eval_data)}] ", end="")
            if final_answer:
                print(f"✅ {final_answer[:50]}")
            else:
                print("❌ No answer")
        
        evaluator.print_report()
        results[mode_name] = evaluator
        
        # Save
        save_path = f"/kaggle/working/eval_{mode_name.lower().replace('-','_')}.csv"
        evaluator.save_to_csv(save_path)
    
    # Comparison table
    print("\n" + "═" * 70)
    print("📊 BẢNG SO SÁNH")
    print("═" * 70)
    print(f"{'Metric':<25} {'BASE':<20} {'FINE-TUNED':<20}")
    print("─" * 70)
    
    for key in ['answer_rate', 'avg_latex_score', 'avg_vn_score', 'avg_time_sec']:
        base_val = results['BASE'].summary().get(key, 0)
        ft_val = results['FINE-TUNED'].summary().get(key, 0)
        print(f"{key:<25} {base_val:<20.2f} {ft_val:<20.2f}")
    
    if 'exact_match' in results['BASE'].summary():
        for key in ['exact_match', 'numerical_match']:
            base_val = results['BASE'].summary().get(key, 0)
            ft_val = results['FINE-TUNED'].summary().get(key, 0)
            print(f"{key:<25} {base_val:<20.2f} {ft_val:<20.2f}")
    
    print("═" * 70)
    
    return results

# ══════════════════════════════════════════════════════════════
# CELL 11.5: Compare BASE vs FINE-TUNED trên cùng 1 bài
# ══════════════════════════════════════════════════════════════
def run_single_pipeline(problem, mode_name, tokenizer):
    """Chạy 1 pipeline (BASE hoặc FINE-TUNED), trả về ctx + final_answer."""
    print(f"\n{'═'*70}")
    print(f"  PIPELINE: {mode_name}")
    print(f"{'═'*70}")

    if mode_name == "BASE":
        model, _, _ = load_model_and_tokenizer(use_finetuned=False)
        adapters = None
    else:
        model, _, adapters = load_model_and_tokenizer(use_finetuned=True)
        if not adapters:
            print(f"[WARN] {mode_name} requested but no adapters found → skip")
            return None, None
        # EDA auto-pick
        if any(len(v) > 1 for v in adapters.values()):
            adapters = auto_pick_best_checkpoints(model, tokenizer, adapters)

    steps_display, final_answer, ctx = solve_math_problem(
        model, tokenizer, problem, adapters
    )

    # Display
    display_solution_beautiful(steps_display, final_answer, problem)
    try:
        display_html_solution(steps_display, final_answer, problem)
    except Exception:
        pass

    gc.collect()
    torch.cuda.empty_cache()
    return ctx, final_answer


def compare_pipelines():
    """
    Chạy song song BASE vs FINE-TUNED trên cùng 1 bài (xác suất thống kê).
    In side-by-side table so sánh từng agent + final answer.
    """
    print("\n" + "═"*70)
    print("   🔬 COMPARE MODE: BASE vs FINE-TUNED")
    print("═"*70)
    print(f"   Problem: {CFG.compare_problem}")

    # Tokenizer dùng chung
    print("\n[Setup] Loading shared tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        CFG.base_model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ── BASE ──
    print("\n[1/2] Running BASE pipeline...")
    base_ctx, base_ans = run_single_pipeline(
        CFG.compare_problem, "BASE", tokenizer)

    # ── FINE-TUNED ──
    print("\n[2/2] Running FINE-TUNED pipeline...")
    ft_ctx, ft_ans = run_single_pipeline(
        CFG.compare_problem, "FINE-TUNED", tokenizer)

    # ── Comparison Table ──
    print("\n" + "═"*70)
    print("   📊 COMPARISON TABLE")
    print("═"*70)
    agents = ["agent1", "agent2", "agent3", "agent4", "agent5"]
    print(f"{'Agent':<8} │ {'BASE (first 50 chars)':<32} │ {'FINE-TUNED (first 50 chars)':<32}")
    print("─"*82)
    for aid in agents:
        b = (base_ctx or {}).get(aid, "(none)")
        f = (ft_ctx or {}).get(aid, "(none)")
        b_short = (b[:30] + "..") if len(b) > 32 else b
        f_short = (f[:30] + "..") if len(f) > 32 else f
        print(f"{aid:<8} │ {b_short:<32} │ {f_short:<32}")
    print("─"*82)
    print(f"{'FINAL':<8} │ {str(base_ans):<32} │ {str(ft_ans):<32}")
    print("═"*70)

    return {"base": base_ctx, "finetuned": ft_ctx,
            "base_answer": base_ans, "ft_answer": ft_ans}


# ══════════════════════════════════════════════════════════════
# ╔══════════════════════════════════════════════════════════════╗
# ║  CELL 0A: LIST CHECKPOINT STRUCTURE (standalone, fast)       ║
# ╚══════════════════════════════════════════════════════════════╝
# Đọc trực tiếp /kaggle/input/datasets/vitduq/train-dataa08082026/outputs
# KHÔNG cần load model. Chỉ liệt kê cây thư mục.
# ══════════════════════════════════════════════════════════════

def list_kaggle_checkpoints(output_root):
    """
    Liệt kê cấu trúc checkpoint dưới `output_root/<agent_id>/<ckpt_name>/`.
    Trả về dict {agent_id: [(ckpt_basename, ckpt_full_path), ...]}.
    KHÔNG load model, KHÔNG filter theo adapter_config — chỉ in ra hết.
    """
    import os

    if not os.path.exists(output_root):
        print(f"❌ Path not found: {output_root}")
        return {}

    print("\n" + "═" * 70)
    print(f"  📂 SCAN: {output_root}")
    print("═" * 70)

    # ── Bước 1: In cấu trúc thô (top 2 level) ──────────────
    print(f"\n  [TOP-LEVEL]")
    try:
        top_entries = sorted(os.listdir(output_root))
    except Exception as e:
        print(f"  ❌ Cannot listdir: {e}")
        return {}

    for entry in top_entries:
        full = os.path.join(output_root, entry)
        if os.path.isdir(full):
            try:
                n_sub = len(os.listdir(full))
                print(f"    📁 {entry}/  ({n_sub} entries)")
            except Exception:
                print(f"    📁 {entry}/")
        else:
            size = os.path.getsize(full)
            print(f"    📄 {entry}  ({size:,} bytes)")

    # ── Bước 2: Group theo agent_id ───────────────────────
    print(f"\n  [PER-AGENT]")
    agents_found = {}
    for entry in top_entries:
        full = os.path.join(output_root, entry)
        if not os.path.isdir(full):
            continue

        agent_id_lower = entry.lower()
        matched_agent = None
        for aid in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
            if aid in agent_id_lower:
                matched_agent = aid
                break

        if matched_agent is None:
            print(f"    ⚠️  Skip (not an agent folder): {entry}/")
            continue

        # List sub-checkpoints inside this agent folder
        ckpts = []
        try:
            for sub in sorted(os.listdir(full)):
                sub_full = os.path.join(full, sub)
                if os.path.isdir(sub_full):
                    # Check bên trong có file gì
                    try:
                        sub_files = sorted(os.listdir(sub_full))
                    except Exception:
                        sub_files = []
                    ckpts.append((sub, sub_full, sub_files))
        except Exception as e:
            print(f"    ⚠️  Cannot listdir {full}: {e}")

        agents_found[matched_agent] = ckpts
        print(f"    📦 {matched_agent}: {len(ckpts)} sub-folder(s)")
        for i, (bn, bfull, bfiles) in enumerate(ckpts):
            has_adapter = "adapter_config.json" in bfiles
            has_weights = any(f.endswith((".safetensors", ".bin")) for f in bfiles)
            flag = "✓" if (has_adapter and has_weights) else "✗"
            print(f"       {i+1}. {flag} {bn}/  "
                  f"[adapter={'Y' if has_adapter else 'N'}, "
                  f"weights={'Y' if has_weights else 'N'}, "
                  f"files={len(bfiles)}]")

    # ── Bước 3: Sort theo ưu tiên (final > checkpoint-N cao) ──
    print(f"\n  [SORTED — by priority: final > checkpoint-N highest]")
    sorted_out = {}
    for aid in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
        if aid not in agents_found:
            sorted_out[aid] = []
            continue

        def _key(item):
            bn = item[0]
            if bn == "final":
                return (0, 0)
            try:
                n = int(bn.split("-")[-1])
                return (1, -n)
            except Exception:
                return (2, 0)

        ckpts_sorted = sorted(agents_found[aid], key=_key)
        sorted_out[aid] = [(bn, bfull) for bn, bfull, _ in ckpts_sorted]

        print(f"    {aid}:")
        for i, (bn, _) in enumerate(ckpts_sorted):
            star = " ★ BEST" if i == 0 else ""
            print(f"       {i+1}. {bn}{star}")

    # ── Bước 4: Summary cho việc chọn path ────────────────
    print(f"\n  [SUMMARY]")
    total_ckpt = sum(len(v) for v in sorted_out.values())
    n_agents_with_ckpt = sum(1 for v in sorted_out.values() if v)
    print(f"    Tổng: {total_ckpt} checkpoint(s) across {n_agents_with_ckpt} agent(s)")

    multi = [a for a, v in sorted_out.items() if len(v) > 1]
    if multi:
        print(f"    ✅ Agents có nhiều checkpoint: {', '.join(multi)}")
        print(f"    → Có thể probe từng cái để chọn tốt nhất")
    elif n_agents_with_ckpt > 0:
        print(f"    ℹ️  Mỗi agent chỉ có 1 checkpoint → dùng luôn")

    print("\n" + "═" * 70)
    return sorted_out


def build_adapter_dict(sorted_ckpts, agent_ids=None):
    """
    Từ output của list_kaggle_checkpoints() → dict {agent_id: ckpt_path}
    cho auto_pick_best_checkpoints() và pipeline inference.
    """
    if agent_ids is None:
        agent_ids = ["agent1", "agent2", "agent3", "agent4", "agent5"]

    out = {}
    for aid in agent_ids:
        ckpts = sorted_ckpts.get(aid, [])
        if not ckpts:
            print(f"  ⚠️  {aid}: no checkpoint")
            continue
        # Mặc định lấy cái đầu tiên (final hoặc cao nhất)
        bn, full = ckpts[0]
        out[aid] = full
        print(f"  {aid} → {bn} ({full})")

    return out
# Chạy TRƯỚC khi load model. Scan tất cả checkpoints mỗi agent,
# liệt kê số lượng + thứ tự ưu tiên (final > checkpoint-N cao).
# Kết quả dùng để quyết định dùng checkpoint nào.
# ══════════════════════════════════════════════════════════════

def eda_checkpoints_only(adapter_base_path):
    """
    Scan và in bảng thống kê checkpoints — KHÔNG load model.
    Trả về dict {agent_id: [(ckpt_name, ckpt_path), ...]} đã sort.
    """
    import os, json

    if not os.path.exists(adapter_base_path):
        print(f"⚠️  Path not found: {adapter_base_path}")
        return {}

    print("\n" + "═" * 70)
    print("  🔍 EDA-A: CHECKPOINT INVENTORY")
    print("═" * 70)
    print(f"  Base path : {adapter_base_path}\n")

    def _find_all_checkpoints(base):
        """Trả về {agent_id: [(basename, full_path), ...]}."""
        result = {}
        for root, dirs, files in os.walk(base):
            if "adapter_config.json" in files:
                for aid in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
                    if aid in root.lower():
                        bn = os.path.basename(root.rstrip(os.sep))
                        result.setdefault(aid, []).append((bn, root))
                        break
        return result

    def _sort_key(item):
        """final=ưu tiên cao nhất, checkpoint-N=sort theo N giảm dần."""
        name = item[0]
        if name == "final":
            return (0, 0)
        try:
            n = int(name.split("-")[-1])
            return (1, -n)
        except Exception:
            return (2, 0)

    raw = _find_all_checkpoints(adapter_base_path)
    sorted_ckpts = {}
    for aid in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
        items = raw.get(aid, [])
        items.sort(key=_sort_key)
        sorted_ckpts[aid] = items

    # ── Bảng tổng quan ────────────────────────────────────────
    total = sum(len(v) for v in sorted_ckpts.values())
    print(f"  Tổng cộng: {total} checkpoint(s) across {sum(len(v)>0 for v in sorted_ckpts.values())} agent(s)\n")

    for aid in ["agent1", "agent2", "agent3", "agent4", "agent5"]:
        items = sorted_ckpts[aid]
        if not items:
            print(f"  ⚠️  {aid}: KHÔNG có checkpoint nào")
            continue
        print(f"  📂 {aid}: {len(items)} checkpoint(s)")
        for i, (bn, full) in enumerate(items):
            star = " ★ BEST" if i == 0 else ""
            # Đọc adapter_config để lấy thông tin
            config_path = os.path.join(full, "adapter_config.json")
            info = ""
            if os.path.exists(config_path):
                try:
                    with open(config_path) as f:
                        cfg = json.load(f)
                    r = cfg.get("r", "?")
                    alpha = cfg.get("lora_alpha", "?")
                    info = f"  [r={r}, α={alpha}]"
                except Exception:
                    pass
            print(f"     {i+1}. {bn}{star}{info}")
        print()

    # ── Summary: agents có nhiều checkpoint → EDA-B có tác dụng ──
    multi = [a for a, v in sorted_ckpts.items() if len(v) > 1]
    if multi:
        print(f"  ✅ Agents có ≥2 checkpoints (nên chạy EDA-B probe): {', '.join(multi)}")
    else:
        print(f"  ℹ️  Mỗi agent chỉ có 1 checkpoint → EDA-B probe sẽ skip.")
        print(f"     Dùng checkpoint mặc định (checkpoint đầu tiên sau sort).")

    print("\n" + "═" * 70)
    return sorted_ckpts


# ══════════════════════════════════════════════════════════════
# ╔══════════════════════════════════════════════════════════════╗
# ║  CELL EDA-B: TRAINING LOSS ANALYSIS (standalone)           ║
# ╚══════════════════════════════════════════════════════════════╝
# Đọc training_history.json từ Kaggle output, vẽ:
#   1. Train loss / eval loss per step (mỗi agent 1 subplot)
#   2. So sánh final loss giữa các agent
#   3. Chẩn đoán: loss không giảm / dao động / overfitting
# ══════════════════════════════════════════════════════════════

def eda_training_loss(history_json_path,
                      plots_dir="plots",
                      figsize=(16, 14)):
    """
    Phân tích training_history.json từ Kaggle training pipeline.
    Vẽ 4 chart: train_loss, eval_loss, lr, so sánh agent.
    """
    import os, json, numpy as np, matplotlib.pyplot as plt

    if not os.path.exists(history_json_path):
        print(f"⚠️  File not found: {history_json_path}")
        print(f"  → Upload training_history.json từ Kaggle output vào workspace")
        return None

    with open(history_json_path) as f:
        history = json.load(f)

    os.makedirs(plots_dir, exist_ok=True)

    agents = sorted(history.keys())
    if not agents:
        print("⚠️  history.json rỗng hoặc sai định dạng")
        return None

    print("\n" + "═" * 70)
    print("  📊 EDA-B: TRAINING LOSS ANALYSIS")
    print("═" * 70)

    # ── Bảng tổng kết loss ────────────────────────────────────
    print(f"\n  {'Agent':<10} {'Final Train Loss':>18} {'Final Eval Loss':>17} "
          f"{'Best Train':>12} {'Best Eval':>11} {'Steps':>7}")
    print(f"  {'-'*76}")

    summary_rows = []
    for aid in agents:
        h = history[aid]
        train_losses = h.get("train_loss", [])
        eval_losses  = h.get("eval_loss", [])
        lr_history   = h.get("learning_rate", [])
        final_train  = train_losses[-1] if train_losses else None
        final_eval   = eval_losses[-1]  if eval_losses  else None
        best_train   = min(train_losses) if train_losses else None
        best_eval    = min(eval_losses)  if eval_losses  else None
        steps        = len(train_losses)

        summary_rows.append({
            "agent": aid,
            "final_train": final_train,
            "final_eval": final_eval,
            "best_train": best_train,
            "best_eval": best_eval,
            "steps": steps,
            "train_loss_list": train_losses,
            "eval_loss_list": eval_losses,
            "lr_list": lr_history,
        })

        ft_s = f"{final_train:.6f}" if final_train is not None else "N/A"
        fe_s = f"{final_eval:.6f}"  if final_eval  is not None else "N/A"
        bt_s = f"{best_train:.6f}"  if best_train  is not None else "N/A"
        be_s = f"{best_eval:.6f}"   if best_eval    is not None else "N/A"
        print(f"  {aid:<10} {ft_s:>18} {fe_s:>17} {bt_s:>12} {be_s:>11} {steps:>7}")

    # ── CHẨN ĐOÁN ─────────────────────────────────────────────
    print(f"\n  {'─'*76}")
    print(f"  🔬 CHẨN ĐOÁN:")
    print(f"  {'─'*76}")

    for row in summary_rows:
        aid   = row["agent"]
        tl    = row["train_loss_list"]
        el    = row["eval_loss_list"]

        issues = []
        if len(tl) < 3:
            issues.append("⚠️  Too few steps (<3) — training quá ngắn")
        elif tl:
            # Check: loss không giảm?
            first_10 = tl[:min(10, len(tl))]
            last_10  = tl[-min(10, len(tl)):]
            if np.mean(last_10) >= np.mean(first_10) * 1.05:
                issues.append("❌ Loss không giảm (có thể overfitting or divergence)")
            # Check: dao động mạnh?
            if len(tl) > 5:
                diffs = [abs(tl[i+1]-tl[i]) for i in range(len(tl)-1)]
                if np.mean(diffs) > 0.5:
                    issues.append(f"⚡ Loss dao động mạnh (avg_Δ={np.mean(diffs):.3f})")
            # Check: eval >> train (overfitting)
            if el and tl:
                if el[-1] > tl[-1] * 2:
                    issues.append(f"📈 Eval >> Train (overfitting rõ rệt)")
            # Check: eval loss tăng
            if len(el) > 3:
                if el[-1] > el[0]:
                    issues.append("📈 Eval loss tăng dần (overfitting)")
            # Check: final loss rất cao
            if tl and tl[-1] > 3.0:
                issues.append(f"🔴 Final train loss cao ({tl[-1]:.1f}) — model chưa học được")
            # Check: final loss rất thấp (< 0.1) — có thể overfit hoàn toàn
            if tl and tl[-1] < 0.1:
                issues.append(f"🟡 Final train loss rất thấp ({tl[-1]:.4f}) — cẩn thận overfit")

        if issues:
            print(f"\n  🔴 {aid}:")
            for iss in issues:
                print(f"     {iss}")
        else:
            print(f"  ✅ {aid}: Loss giảm ổn định, không có dấu hiệu overfitting nghiêm trọng")

    # ── Vẽ đồ thị ───────────────────────────────────────────────
    # Layout: 2 plot overview (train_all, eval_all) + grid 3x2 cho 5 agents
    # Tạo 2 figure riêng cho dễ nhìn
    n_agents = len(agents)
    colors = plt.cm.tab10(np.linspace(0, 1, n_agents))

    # ═══ FIGURE 1: Overview — train loss + eval loss all agents ═══
    fig1, axes1 = plt.subplots(1, 2, figsize=(14, 5))
    fig1.suptitle("Training Loss — Overview (all agents)",
                  fontsize=14, fontweight="bold")

    # Plot 1A: Train Loss — tất cả agent trên 1 axes
    ax = axes1[0]
    for i, aid in enumerate(agents):
        tl = summary_rows[i]["train_loss_list"]
        if tl:
            steps_ = range(1, len(tl)+1)
            ax.plot(steps_, tl, label=aid, color=colors[i], linewidth=1.5)
    ax.set_xlabel("Step")
    ax.set_ylabel("Train Loss")
    ax.set_title("Train Loss — All Agents")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Plot 1B: Eval Loss — tất cả agent
    ax = axes1[1]
    has_eval = False
    for i, aid in enumerate(agents):
        el = summary_rows[i]["eval_loss_list"]
        if el:
            has_eval = True
            steps_ = range(1, len(el)+1)
            ax.plot(steps_, el, label=aid, color=colors[i],
                    linewidth=1.5, marker="o", markersize=3)
    if has_eval:
        ax.set_xlabel("Eval Step")
        ax.set_ylabel("Eval Loss")
        ax.set_title("Eval Loss — All Agents")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    else:
        ax.text(0.5, 0.5, "No eval loss\nin history.json",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Eval Loss — (no data)")

    fig1.tight_layout()
    fig1_path = os.path.join(plots_dir, "05a_overview_loss.png")
    fig1.savefig(fig1_path, bbox_inches="tight", facecolor="white")
    plt.show()
    print(f"\n  [OK] Chart saved: {fig1_path}")

    # ═══ FIGURE 2: Per-agent grid (3 hàng x 2 cột, slot 6) ═══
    n_rows = (n_agents + 1) // 2
    fig2, axes2 = plt.subplots(n_rows, 2, figsize=(14, 4 * n_rows))
    fig2.suptitle("Per-Agent Loss Curves (train + eval)",
                  fontsize=14, fontweight="bold")

    # Flat axes2 để dễ iterate
    axes_flat = axes2.flat if n_rows > 1 else [axes2[0], axes2[1]]
    if n_agents == 1:
        axes_flat = [axes2]

    for idx in range(6):
        ax = axes_flat[idx]
        if idx < n_agents:
            aid = agents[idx]
            tl = summary_rows[idx]["train_loss_list"]
            el = summary_rows[idx]["eval_loss_list"]
            c  = colors[idx]

            if tl:
                ax.plot(range(1, len(tl)+1), tl, label="train",
                        color=c, linewidth=1.2)
            if el:
                ax.plot(range(1, len(el)+1), el, label="eval",
                        color=c, linewidth=1.2, linestyle="--",
                        marker="o", markersize=2)
            ax.set_title(f"{aid}", fontsize=11, fontweight="bold")
            ax.set_xlabel("Step")
            ax.set_ylabel("Loss")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)

            # Annotate final loss
            if tl:
                ax.axhline(tl[-1], color=c, linestyle=":", alpha=0.4)
                ax.text(0.02, 0.05, f"final train: {tl[-1]:.4f}",
                        transform=ax.transAxes, fontsize=8,
                        bbox=dict(boxstyle="round,pad=0.3",
                                  facecolor="white", alpha=0.8))
        else:
            # Subplot thừa — ẩn
            ax.set_visible(False)

    fig2.tight_layout()
    fig2_path = os.path.join(plots_dir, "05b_per_agent_loss.png")
    fig2.savefig(fig2_path, bbox_inches="tight", facecolor="white")
    plt.show()
    print(f"  [OK] Chart saved: {fig2_path}")

    # ── Bảng so sánh agent tốt nhất ─────────────────────────────
    print(f"\n  {'─'*76}")
    print(f"  🏆 RANKING theo Final Eval Loss (thấp = tốt):")
    print(f"  {'─'*76}")
    ranked = [(r["agent"], r["final_eval"], r["best_eval"])
              for r in summary_rows if r["final_eval"] is not None]
    ranked.sort(key=lambda x: x[1])
    for rank, (aid, fe, be) in enumerate(ranked, 1):
        delta = (fe - be) / be * 100 if be else 0
        print(f"     {rank}. {aid:<10} final={fe:.6f}  best={be:.6f}  "
              f"(+{delta:.1f}% gap)")
    if not ranked:
        print("     (Không có eval loss — chỉ xếp hạng bằng train loss)")
        ranked_train = [(r["agent"], r["final_train"])
                        for r in summary_rows if r["final_train"] is not None]
        ranked_train.sort(key=lambda x: x[1])
        for rank, (aid, ft) in enumerate(ranked_train, 1):
            print(f"     {rank}. {aid:<10} final_train={ft:.6f}")

    print("\n" + "═" * 70)
    return summary_rows


# ══════════════════════════════════════════════════════════════
# CELL 12: Main Demo
# ══════════════════════════════════════════════════════════════
def main():
    print("\n" + "═" * 70)
    print("   5-AGENT MATH SOLVER")
    print("   Base Model + Fine-tuned Support")
    print("═" * 70)

    # ─────────────────────────────────────────────────────────
    # COMPARE MODE: BASE vs FINE-TUNED trên cùng 1 bài
    # ─────────────────────────────────────────────────────────
    if CFG.compare_mode:
        compare_pipelines()
        print("\n" + "═" * 70)
        print("   HOÀN THÀNH COMPARE MODE!")
        print("═" * 70)
        return

    # ─────────────────────────────────────────────────────────
    # SINGLE PIPELINE MODE (giữ nguyên flow cũ)
    # ─────────────────────────────────────────────────────────
    # Load model
    model, tokenizer, adapters = load_model_and_tokenizer(CFG.use_finetuned)

    # EDA: scan tất cả checkpoints mỗi agent, auto-pick cái tốt nhất
    if adapters and any(len(v) > 1 for v in adapters.values()):
        adapters = auto_pick_best_checkpoints(model, tokenizer, adapters)

    mode = "FINE-TUNED" if adapters else "BASE MODEL"
    print(f"\n✅ Model loaded: {mode}")
    print(f"   Adapters: {list(adapters.keys()) if adapters else 'None'}")
    
    # Test problems
    test_problems = [
        "Giải phương trình: $x^2 - 5x + 6 = 0$",
        "Tính đạo hàm: $f(x) = x^3 + 2x^2 - x + 1$",
        "Cho $a = 3$, $b = 4$. Tính $\\sqrt{a^2 + b^2}$",
    ]
    
    evaluator = MathEvaluator()
    
    for i, problem in enumerate(test_problems, 1):
        print(f"\n{'#' * 70}")
        print(f"# BÀI TOÁN {i}")
        print(f"{'#' * 70}")
        
        # Solve
        start = time.time()
        steps_display, final_answer, ctx = solve_math_problem(
            model, tokenizer, problem, adapters
        )
        elapsed = time.time() - start
        
        # Display
        display_solution_beautiful(steps_display, final_answer, problem)
        display_html_solution(steps_display, final_answer, problem)
        
        # Evaluate
        solution_text = "\n".join([c for _, c in steps_display])
        result = evaluator.evaluate(problem, final_answer, solution_text, time_taken=elapsed)
        
        gc.collect()
        torch.cuda.empty_cache()
        
        if i >= 2:
            break
    
    # Print report
    evaluator.print_report()
    evaluator.save_to_csv("/kaggle/working/eval_results.csv")
    
    print("\n" + "═" * 70)
    print("   HOÀN THÀNH!")
    print("═" * 70)

if __name__ == "__main__":
    main()
