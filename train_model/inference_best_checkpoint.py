"""
5-Agent Math Solver - Best Checkpoint Inference
- Load best checkpoint (lowest train loss) per agent
- Force Vietnamese solving with LaTeX formatting
- Output: clear step-by-step solution with beautiful LaTeX
"""

import os
import json
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel


# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════
class CFG:
    # Base model
    base_model_name = "Qwen/Qwen2.5-Math-1.5B-Instruct"

    # Output dir từ training (chứa {agent}_best/)
    outputs_dir = "train_model/outputs"

    # Best checkpoint per agent (auto-detected if exists)
    use_best_checkpoint = True

    # Generation settings
    max_new_tokens = 1024
    temperature = 0.3
    top_p = 0.9
    top_k = 50
    repetition_penalty = 1.2
    do_sample = True

    # Vietnamese + LaTeX system prompt
    system_prompt = (
        "Bạn là gia sư toán học tiếng Việt. Hãy giải bài toán theo các bước rõ ràng, "
        "trình bày đẹp bằng LaTeX. Yêu cầu:\n"
        "- **Bước 1**: Phân tích đề bài (liệt kê dữ kiện, yêu cầu).\n"
        "- **Bước 2**: Lập phương pháp giải (công thức, định lý áp dụng).\n"
        "- **Bước 3**: Trình bày lời giải chi tiết với mỗi phép tính kèm LaTeX "
        "($x^2$, $\\frac{a}{b}$, $\\sqrt{n}$, $\\int$, $\\sum$, ...).\n"
        "- **Bước 4**: Kiểm tra lại và ghi đáp án cuối cùng trong khung $\\boxed{...}$.\n"
        "- Chỉ dùng tiếng Việt, dùng ký hiệu toán học LaTeX chuẩn cho công thức. "
        "Mỗi bước trên 1 dòng riêng. Không lặp lại nội dung."
    )

    # Adapter paths (priority: best -> final)
    agents = ["agent1", "agent2", "agent3", "agent4", "agent5"]


# ══════════════════════════════════════════════════════════════
# LOAD MODEL + BEST ADAPTERS
# ══════════════════════════════════════════════════════════════
def find_best_adapter(outputs_dir, agent_id):
    """Tìm best checkpoint cho agent, fallback về final."""
    best_dir = os.path.join(outputs_dir, f"{agent_id}_best")
    final_dir = os.path.join(outputs_dir, agent_id)

    if CFG.use_best_checkpoint and os.path.exists(best_dir):
        # Đọc metadata để log
        meta_path = os.path.join(best_dir, "best_checkpoint.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            print(f"   [BEST] {agent_id}: step={meta.get('best_step')}, "
                  f"loss={meta.get('best_loss', 0):.6f}")
        return best_dir
    elif os.path.exists(final_dir):
        print(f"   [FINAL] {agent_id}: {final_dir}")
        return final_dir
    else:
        return None


def load_model_with_best_adapters():
    print("=" * 70)
    print("LOAD MODEL + BEST ADAPTERS")
    print("=" * 70)

    # Tokenizer
    print(f"\n[1] Loading tokenizer from {CFG.base_model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(
        CFG.base_model_name, trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Base model
    print(f"[2] Loading base model...")
    model = AutoModelForCausalLM.from_pretrained(
        CFG.base_model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    model.eval()

    # Load adapters
    print(f"[3] Loading best adapters from {CFG.outputs_dir}...")
    adapters = {}
    for agent_id in CFG.agents:
        adapter_path = find_best_adapter(CFG.outputs_dir, agent_id)
        if adapter_path is None:
            print(f"   [SKIP] {agent_id}: no checkpoint found")
            continue
        adapters[agent_id] = adapter_path
        print(f"   [OK] {agent_id} -> {adapter_path}")

    if not adapters:
        raise RuntimeError(f"No adapters found in {CFG.outputs_dir}")

    return model, tokenizer, adapters


# ══════════════════════════════════════════════════════════════
# INFERENCE
# ══════════════════════════════════════════════════════════════
def build_prompt(problem, tokenizer):
    """Build chat prompt with Vietnamese+LaTeX system instruction."""
    messages = [
        {"role": "system", "content": CFG.system_prompt},
        {"role": "user", "content": f"Giải bài toán sau:\n\n{problem}"},
    ]
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    return prompt


def solve_single_agent(model, tokenizer, adapter_path, problem, agent_label=""):
    """Solve problem with a single adapter."""
    prompt = build_prompt(problem, tokenizer)

    # Load adapter
    model.load_adapter(adapter_path, adapter_name="active")

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    prompt_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=CFG.max_new_tokens,
            temperature=CFG.temperature,
            top_p=CFG.top_p,
            top_k=CFG.top_k,
            repetition_penalty=CFG.repetition_penalty,
            do_sample=CFG.do_sample,
            pad_token_id=tokenizer.pad_token_id,
        )

    # Decode only the generated part
    response = tokenizer.decode(
        outputs[0][prompt_len:], skip_special_tokens=True
    )

    # Unload to free memory
    model.unload()

    return response


def solve_pipeline(model, tokenizer, adapters, problem):
    """Run 5-agent pipeline: each agent refines the answer."""
    history = []
    current = problem

    pipeline_steps = [
        ("agent1", "Gợi ý bước"),
        ("agent2", "Phân loại dạng"),
        ("agent3", "Suy luận"),
        ("agent4", "Trình bày LaTeX"),
        ("agent5", "Kiểm tra"),
    ]

    for agent_id, role in pipeline_steps:
        if agent_id not in adapters:
            continue
        adapter_path = adapters[agent_id]

        # Build prompt with context
        if agent_id == "agent1":
            prompt = problem
        else:
            context = "\n\n".join(
                f"[{r['role']}]: {r['output']}" for r in history
            )
            prompt = (
                f"Bài toán gốc:\n{problem}\n\n"
                f"Các bước trước:\n{context}\n\n"
                f"Bây giờ vai trò của bạn: {role}. "
                f"Tiếp tục và làm rõ hơn, trình bày LaTeX đẹp. "
                f"Trả lời tiếng Việt."
            )

        print(f"\n>>> [AGENT {agent_id[-1]}] {role}...")
        response = solve_single_agent(
            model, tokenizer, adapter_path, prompt, agent_id
        )
        history.append({"agent": agent_id, "role": role, "output": response})

    # Final answer = last agent's output
    return history[-1]["output"] if history else "", history


# ══════════════════════════════════════════════════════════════
# DISPLAY (render LaTeX in Jupyter)
# ══════════════════════════════════════════════════════════════
def render_solution(problem, final_answer, history=None):
    """Pretty-print with LaTeX rendering."""
    print("\n" + "=" * 70)
    print("BÀI TOÁN")
    print("=" * 70)
    print(problem)

    if history:
        print("\n" + "=" * 70)
        print("PIPELINE (5 AGENTS)")
        print("=" * 70)
        for h in history:
            print(f"\n--- [{h['agent'].upper()}] {h['role']} ---")
            print(h["output"])

    print("\n" + "=" * 70)
    print("LỜI GIẢI CUỐI CÙNG")
    print("=" * 70)
    print(final_answer)

    # Try to render LaTeX in Jupyter
    try:
        from IPython.display import display, Markdown
        display(Markdown(final_answer))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# INTERACTIVE INPUT
# ══════════════════════════════════════════════════════════════
def get_problem_interactive():
    """Nhập bài toán - hỗ trợ cả Jupyter widget và terminal."""
    # Thử Jupyter widget trước (đẹp hơn)
    try:
        import ipywidgets as widgets
        from IPython.display import display, clear_output

        ta = widgets.Textarea(
            value="",
            placeholder="Nhập đề bài toán tiếng Việt vào đây...\n\n"
                        "VD: Giải phương trình $x^2 - 5x + 6 = 0$\n"
                        "VD: Tính $\\int_0^1 x^2 dx$\n"
                        "VD: Cho tam giác ABC vuông tại A, AB=3, AC=4. Tính BC.",
            description="Bài toán:",
            layout=widgets.Layout(width="95%", height="120px"),
        )
        btn = widgets.Button(
            description="Giải", button_style="success", icon="check"
        )
        out = widgets.Output()

        def on_click(_):
            with out:
                clear_output()
                problem = ta.value.strip()
                if not problem:
                    print("Vui lòng nhập bài toán!")
                    return
                final, hist = solve_pipeline(CACHED["model"], CACHED["tok"],
                                              CACHED["adapters"], problem)
                render_solution(problem, final, hist)

        btn.on_click(on_click)
        display(widgets.VBox([ta, btn, out]))
        return None  # signal: đã show widget
    except ImportError:
        pass

    # Fallback: terminal input (vòng lặp)
    print("\n" + "=" * 70)
    print("NHẬP BÀI TOÁN (gõ 'quit' để thoát, 'test' để chạy test cases)")
    print("=" * 70)
    while True:
        try:
            print()
            problem = input(">> Bài toán: ").strip()
        except EOFError:
            break
        if not problem:
            continue
        if problem.lower() in ("quit", "exit", "q"):
            break
        if problem.lower() == "test":
            run_test_cases(CACHED["model"], CACHED["tok"], CACHED["adapters"])
            continue
        final, hist = solve_pipeline(CACHED["model"], CACHED["tok"],
                                      CACHED["adapters"], problem)
        render_solution(problem, final, hist)
    return None


def run_test_cases(model, tokenizer, adapters):
    test_problems = [
        "Giải phương trình bậc hai: $x^2 - 5x + 6 = 0$",
        "Tính tích phân $\\int_0^1 x^2 \\, dx$",
        "Cho tam giác ABC vuông tại A, AB = 3, AC = 4. Tính độ dài BC.",
        "Rút gọn biểu thức: $\\frac{x^2 - 1}{x - 1}$ với $x \\neq 1$",
        "Một hộp có 5 bi đỏ và 3 bi xanh. Lấy ngẫu nhiên 2 bi không hoàn lại. "
        "a) Tính xác suất để cả 2 bi đều đỏ. "
        "b) Nếu biết bi thứ nhất là bi đỏ, tính xác suất bi thứ hai cũng là bi đỏ.",
    ]
    for i, problem in enumerate(test_problems, 1):
        print(f"\n\n{'#' * 70}")
        print(f"# TEST CASE {i}")
        print(f"{'#' * 70}")
        final, hist = solve_pipeline(model, tokenizer, adapters, problem)
        render_solution(problem, final, hist)


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
# Cache model để widget callback truy cập
CACHED = {}


def main():
    model, tokenizer, adapters = load_model_with_best_adapters()
    CACHED["model"] = model
    CACHED["tok"] = tokenizer
    CACHED["adapters"] = adapters

    get_problem_interactive()


if __name__ == "__main__":
    main()
