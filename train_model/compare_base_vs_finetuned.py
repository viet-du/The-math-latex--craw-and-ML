"""
train_model/compare_base_vs_finetuned.py
Compare BASE Qwen2.5-Math-1.5B-Instruct vs FINE-TUNED LoRA (5-agent adapter)
side-by-side on the same Vietnamese math problem.

The base model is loaded exactly once.  If local LoRA adapters are found,
they are loaded on top of that same base model, one named adapter per agent.
"""

import importlib.util
import os
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Force UTF-8 for Windows consoles and log files.
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import torch

ROOT = Path(__file__).resolve().parents[1]
PROBLEM = "Tính đạo hàm: $f(x) = x^3 + 2x^2 - x + 1$"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_DIR = ROOT / "archive" / "logs"
LOG_PATH = LOG_DIR / f"compare_base_vs_finetuned_{TIMESTAMP}.log"

# This is the same configuration and prompt source used by inference_vietnamese.py.
# A fallback keeps the requested base-only comparison usable when peft is absent.
DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-Math-1.5B-Instruct"
DEFAULT_ADAPTER_PATH = "./outputs"
DEFAULT_AGENT_TOKEN_CAPS = {
    "agent1": 96,
    "agent2": 32,
    "agent3": 192,
    "agent4": 128,
    "agent5": 64,
}
DEFAULT_AGENT_MAX_TOKENS = 256
DEFAULT_REPETITION_PENALTY = 1.3
DEFAULT_NO_REPEAT_NGRAM_SIZE = 4
DEFAULT_AGENT_LABELS = {
    "agent1": "BƯỚC 1 - AGENT 1 (Chuẩn hóa)",
    "agent2": "BƯỚC 2 - AGENT 2 (Phân loại)",
    "agent3": "BƯỚC 3 - AGENT 3 (Suy luận)",
    "agent4": "BƯỚC 4 - AGENT 4 (Trình bày)",
    "agent5": "BƯỚC 5 - AGENT 5 (Kiểm tra)",
}
DEFAULT_AGENT_PROMPTS = {
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

console_lines = []
errors = []
base_results = {}
ft_results = {}
base_final_answer = None
ft_final_answer = None
adapter_paths = {}
adapter_status = "Not checked"
inf = None


def emit(text=""):
    """Print UTF-8 text and retain it for the UTF-8 comparison log."""
    text = str(text)
    console_lines.append(text)
    print(text, flush=True)


def load_inference_config():
    """Import inference_vietnamese without executing its CLI entry point."""
    global inf
    config_path = ROOT / "train_model" / "inference_vietnamese.py"
    spec = importlib.util.spec_from_file_location("inf_vi_compare", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import inference config: {config_path}")
    inf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inf)
    emit(f"Shared config: {config_path}")
    return inf


def get_config_value(name, default):
    if inf is not None and hasattr(inf, "CFG"):
        return getattr(inf.CFG, name, default)
    return default


def get_prompts():
    if inf is not None and hasattr(inf, "AGENT_PROMPTS"):
        return inf.AGENT_PROMPTS
    return DEFAULT_AGENT_PROMPTS


def adapter_search_roots(configured_path):
    """Return likely local adapter roots, resolving relative paths from project root."""
    configured = Path(str(configured_path)).expanduser()
    if not configured.is_absolute():
        configured = ROOT / configured

    candidates = [
        configured,
        ROOT / "outputs",
        ROOT / "archive" / "outputs",
        ROOT / "archive",
        ROOT / "train_model" / "outputs",
    ]
    unique = []
    seen = set()
    for path in candidates:
        try:
            key = str(path.resolve()).lower()
        except OSError:
            key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def discover_adapters(configured_path):
    """Find direct or per-agent PEFT adapter directories in the local project."""
    found = {}
    visited = set()
    skip_parts = {".git", ".venv", "venv", "node_modules", "__pycache__"}

    for search_root in adapter_search_roots(configured_path):
        if not search_root.exists():
            continue
        paths = [search_root] if (search_root / "adapter_config.json").is_file() else []
        if search_root.is_dir():
            try:
                paths.extend(
                    p for p in search_root.rglob("adapter_config.json")
                    if not any(part.lower() in skip_parts for part in p.parts)
                )
            except OSError as exc:
                emit(f"[WARN] Could not scan {search_root}: {exc}")

        for config_file in paths:
            adapter_dir = config_file.parent.resolve()
            key_path = str(adapter_dir).lower()
            if key_path in visited:
                continue
            visited.add(key_path)
            agent_id = next(
                (part.lower() for part in adapter_dir.parts if part.lower() in DEFAULT_AGENT_LABELS),
                None,
            )
            key = agent_id or "shared"
            if key not in found:
                found[key] = adapter_dir
    return found


def extract_boxed(text):
    """Extract the first simple or one-level-nested \\boxed{...} value."""
    if not text:
        return None
    match = re.search(r"\\boxed\{((?:[^{}]|\{[^{}]*\})*)\}", text)
    return match.group(1).strip() if match else None


def model_input_device(model):
    try:
        return next(model.parameters()).device
    except StopIteration:
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def run_pipeline(model, tokenizer, problem, label, adapter_for_agent=None):
    """Run the exact five independent prompt/generation passes for one model."""
    prompts = get_prompts()
    emit("\n" + "=" * 78)
    emit(f"  PIPELINE: {label}")
    emit("=" * 78)
    results = {}

    for agent_id, agent_prompt in prompts.items():
        if adapter_for_agent and hasattr(model, "set_adapter"):
            model.set_adapter(adapter_for_agent.get(agent_id, adapter_for_agent.get("shared")))

        cap = get_config_value("agent_token_caps", DEFAULT_AGENT_TOKEN_CAPS).get(
            agent_id, get_config_value("agent_max_tokens", DEFAULT_AGENT_MAX_TOKENS)
        )
        messages = [
            {"role": "system", "content": agent_prompt},
            {"role": "user", "content": problem},
        ]
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt, return_tensors="pt")
        input_device = model_input_device(model)
        inputs = {key: value.to(input_device) for key, value in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=cap,
                do_sample=False,
                repetition_penalty=get_config_value(
                    "repetition_penalty", DEFAULT_REPETITION_PENALTY
                ),
                no_repeat_ngram_size=get_config_value(
                    "no_repeat_ngram_size", DEFAULT_NO_REPEAT_NGRAM_SIZE
                ),
                pad_token_id=tokenizer.pad_token_id,
            )
        response = tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        ).strip()
        results[agent_id] = response
        emit(f"\n{('🟢' if 'FINE' in label else '🔵')} {DEFAULT_AGENT_LABELS.get(agent_id, agent_id)}:")
        emit(response or "(empty output)")

        final = extract_boxed(results.get("agent5", ""))
        boxed_text = "\\boxed{" + final + "}" if final else "(không tìm thấy \\boxed{...})"
        emit(f"\nĐÁP ÁN CUỐI CÙNG: {boxed_text}")
        return results, final


def make_comparison_table():
    """Create a compact three-column table while keeping full outputs above."""
    prompts = get_prompts()
    lines = ["\n" + "=" * 78, "  COMPARISON TABLE", "=" * 78]
    lines.append(f"{'agent':<8} | {'base':<52} | {'finetuned':<52}")
    lines.append("-" * 120)
    for agent_id in prompts:
        base_short = " ".join(base_results.get(agent_id, "(none)").split())
        ft_short = " ".join(ft_results.get(agent_id, "(no adapter)").split())
        if len(base_short) > 50:
            base_short = base_short[:47] + "..."
        if len(ft_short) > 50:
            ft_short = ft_short[:47] + "..."
        lines.append(f"{agent_id:<8} | {base_short:<52} | {ft_short:<52}")
    lines.append(f"\nBase agent5 boxed answer: {base_final_answer or '(none)'}")
    lines.append(f"Fine-tuned agent5 boxed answer: {ft_final_answer or '(no adapter)'}")
    return "\n".join(lines)


def save_log():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("w", encoding="utf-8", newline="\n") as log_file:
        log_file.write("BASE VS FINE-TUNED 5-AGENT COMPARISON\n")
        log_file.write(f"Timestamp: {TIMESTAMP}\n")
        log_file.write(f"Problem: {PROBLEM}\n")
        log_file.write(f"Adapter status: {adapter_status}\n")
        if errors:
            log_file.write("\nERRORS:\n")
            for error in errors:
                log_file.write(error.rstrip() + "\n")
        log_file.write("\n" + "\n".join(console_lines) + "\n")
    print(f"\n✅ Saved comparison log: {LOG_PATH}", flush=True)


def main():
    global adapter_paths, adapter_status, base_results, ft_results
    global base_final_answer, ft_final_answer

    emit(f"Project root: {ROOT}")
    emit(f"Problem: {PROBLEM}")
    emit(f"Device: {'cuda' if torch.cuda.is_available() else 'cpu'}")
    if torch.cuda.is_available():
        emit(f"CUDA device: {torch.cuda.get_device_name(0)}")

    configured_adapter = get_config_value("adapter_path", DEFAULT_ADAPTER_PATH)
    emit(f"Configured adapter path: {configured_adapter}")
    emit("Searching local adapter locations...")
    adapter_paths = discover_adapters(configured_adapter)
    if adapter_paths:
        adapter_status = "Found: " + ", ".join(f"{k}={v}" for k, v in adapter_paths.items())
        emit(adapter_status)
    else:
        adapter_status = "No adapter found locally; only base model evaluated."
        emit(adapter_status)

    try:
        load_inference_config()
    except Exception as exc:
        config_error = f"[WARN] Could not import inference_vietnamese.py ({type(exc).__name__}: {exc})"
        emit(config_error)
        errors.append(traceback.format_exc())
        emit("[INFO] Using embedded fallback prompts/configuration.")

    # Import transformers only after config discovery so peft import problems can
    # still produce a useful base-only log.
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as exc:
        errors.append(traceback.format_exc())
        emit(f"[ERROR] transformers import failed: {exc}")
        return

    base_model_name = get_config_value("base_model_name", DEFAULT_BASE_MODEL)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    emit(f"Loading base model once: {base_model_name}")
    model_kwargs = {
        "trust_remote_code": True,
        "torch_dtype": torch.float16 if device == "cuda" else torch.float32,
    }
    if device == "cuda":
        model_kwargs["device_map"] = "auto"

    try:
        tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        base_model = AutoModelForCausalLM.from_pretrained(base_model_name, **model_kwargs)
        base_model.eval()
        base_results, base_final_answer = run_pipeline(
            base_model, tokenizer, PROBLEM, "BASE Qwen2.5-Math-1.5B (no fine-tuning)"
        )
    except Exception as exc:
        errors.append(traceback.format_exc())
        emit(f"[ERROR] Base model inference failed: {exc}")
        return

    # Do not import or load PEFT unless a local adapter was actually found.
    if not adapter_paths:
        ft_results = {}
        ft_final_answer = None
        return

    try:
        from peft import PeftModel
    except Exception as exc:
        adapter_status = f"No fine-tuned run: peft import failed ({type(exc).__name__}: {exc})"
        errors.append(traceback.format_exc())
        emit(f"[WARN] {adapter_status}")
        emit("[INFO] Falling back to base-only; no adapter was applied.")
        return

    try:
        emit("\nLoading fine-tuned adapters on top of the already loaded base model...")
        ordered = sorted(adapter_paths.items(), key=lambda item: item[0])
        # A directory with no agent component is a shared adapter for every pass.
        first_key, first_path = ordered[0]
        first_name = first_key if first_key != "shared" else "shared"
        ft_model = PeftModel.from_pretrained(
            base_model, str(first_path), adapter_name=first_name
        )
        adapter_for_agent = {}
        for agent_id in get_prompts():
            adapter_for_agent[agent_id] = first_name
        if first_key in get_prompts():
            adapter_for_agent[first_key] = first_name

        for key, path in ordered[1:]:
            adapter_name = key
            if adapter_name in getattr(ft_model, "peft_config", {}):
                adapter_name = f"{key}_extra"
            ft_model.load_adapter(str(path), adapter_name=adapter_name)
            if key in get_prompts():
                adapter_for_agent[key] = adapter_name

        ft_model.eval()
        emit("Loaded adapters: " + ", ".join(sorted(getattr(ft_model, "peft_config", {}).keys())))
        ft_results, ft_final_answer = run_pipeline(
            ft_model, tokenizer, PROBLEM, "FINE-TUNED 5-agent LoRA", adapter_for_agent
        )
    except Exception as exc:
        adapter_status = f"Adapter loading/inference failed: {type(exc).__name__}: {exc}"
        errors.append(traceback.format_exc())
        emit(f"[ERROR] {adapter_status}")
        emit("[INFO] Base results remain available; fine-tuned outputs are unavailable.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        errors.append(traceback.format_exc())
        emit(f"[FATAL] {type(exc).__name__}: {exc}")
    finally:
        comparison = make_comparison_table()
        emit(comparison)
        save_log()
