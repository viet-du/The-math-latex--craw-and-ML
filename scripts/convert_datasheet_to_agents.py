"""
Convert datasheet.json to 5-agent training data with train/val split.
Doc datasheet.json va tao data cho 5 agents voi phan chia train/val.
"""

import json
import os
import random
import re
from typing import Dict, List

# ============================================================
# System prompts cho 5 agents
# ============================================================

SYSTEM_PROMPTS = {
    "agent1": """Ban la GIAO SU TOAN HOC VIET NAM.
Nhiem vu: CHUAN HOA bai toan tu loi van sang dinh dang toan hoc.

CHI DUNG TIENG VIET. KHONG DUNG TIENG ANH.

Yeu cau:
1. Chuyen doi ngon ngu tu nhien → ky hieu toan hoc
2. Viet tat ca cong thuc bang LaTeX chuan ($...$ hoac $$...$$)
3. Xac dinh ro: bien so, hang so, dieu kien
4. Giu nguyen y nghia bai toan""",

    "agent2": """Ban la GIAO VIEN TOAN HOC VIET NAM.
Nhiem vu: PHAN LOAI bai toan va xac dinh rang buoc.

CHI DUNG TIENG VIET. KHONG DUNG TIENG ANH.

Yeu cau:
1. Xac dinh LINH VUC: dai so | phan so | giai tich | xac suat thong ke | hinh hoc | luong giac
2. Xac dinh MUC DO: de | trung binh | kho
3. Xac dinh PHUONG PHAP giai phu hop
4. Liet ke DIEU KIEN RANG BUOC""",

    "agent3": """Ban la GIAO SU TOAN HOC VIET NAM.
Nhiem vu: TRINH BAY SUY LUAN TUNG BUOC de giai bai toan.

CHI DUNG TIENG VIET. KHONG DUNG TIENG ANH.

QUY TAC BAT BUOC:
1. Moi buoc phai co so thu tu ro rang: "Buoc 1:", "Buoc 2:", ...
2. Moi buoc phai co cong thuc LaTeX ro rang
3. Moi buoc phai co giai thich TAI SAO bang tieng Viet
4. SUY LUAN PHAI LOGIC, tung buoc ro rang nhu mot nguoi thay dang giang

Format:
"Buoc 1: [cong thuc/toan] - [giai thich tai sao]
 Buoc 2: [cong thuc/toan] - [giai thich]
 ...""",

    "agent4": """Ban la GIAO VIEN TOAN CHI TIET VIET NAM.
Nhiem vu: TRINH BAY LOI GIAI HOAN CHINH theo phong cach su pham.

CHI DUNG TIENG VIET. KHONG DUNG TIENG ANH.

Ket qua cuoi cung phai trong \\boxed{...}
Tat ca cong thuc dung LaTeX
Giai thich bang tieng Viet""",

    "agent5": """Ban la KIEM TRA VIEN CHAT LUONG VIET NAM.
Nhiem vu: XAC MINH va DANH GIA loi giai.

CHI DUNG TIENG VIET. KHONG DUNG TIENG ANH.

Kiem tra:
1. Loi giai co \\boxed{} khong?
2. Noi dung \boxed{} co chinh xac khong?
3. Cac buoc co LOGIC khong?

Tra loi:
- Kiem tra: [PASS/FAIL]
- Dap an xac minh: \\boxed{...}"""
}


# ============================================================
# FIX A: Diversified agent3 fallback
# ============================================================
# In 5agent_expanded the agent3 training target collapsed to a single
# static paragraph for 65.5% of rows, which biased the LoRA toward
# pure memorisation. We now rotate per-math-type templates so the
# fallback is no longer mode-collapsed.
_AGENT3_FALLBACK_POOL = {
    "default": [
        "Buoc 1: Xac dinh dung ban chat cua bai toan va nhan dien cong thuc nen tang can ap dung.",
        "Buoc 2: Phan tich cac du kien da cho de biet dau la bien, dau la hang so va dau la dieu kien xac dinh.",
        "Buoc 3: Bien doi bieu thuc theo duong loi toan hoc phu hop va giu nguyen y nghia cua bai toan.",
        "Buoc 4: Rut gon ket qua va trinh bay dap an o dang chuan, de doc va de kiem tra.",
    ],
    "algebra": [
        "Buoc 1: Ghi ro bieu thuc dai so can xu ly va khai trien cac thanh phan.",
        "Buoc 2: Quy dong, phan tich thua so hoac ap dung hang dang thuc neu can.",
        "Buoc 3: Rut gon tung ve va thu gon bieu thuc ve dang don gian nhat.",
        "Buoc 4: Kiem tra bang phep the gia tri hoac doi chieu voi dieu kien ban dau.",
    ],
    "geometry": [
        "Buoc 1: Ve hinh va ghi nhan cac yeu to hinh hoc da cho (canh, goc, duong cao, ...).",
        "Buoc 2: Xac dinh cac dinh ly/tinh chat co the ap dung (dong dang, Pitago, ...).",
        "Buoc 3: Thiet lap he thuc giua cac doan thang, goc, dien tich hoac the tich.",
        "Buoc 4: Tinh toan va trinh bay ket qua cuoi cung.",
    ],
    "calculus": [
        "Buoc 1: Xac dinh loai bai toan giai tich (dao ham, tich phan, gioi han).",
        "Buoc 2: Ap dung quy tac tuong ung (chuyen dinh ly co ban, ...).",
        "Buoc 3: Tinh toan tung buoc va ghi ro cac phep bien doi trung gian.",
        "Buoc 4: Don gian hoa ket qua va doi chieu voi mien xac dinh.",
    ],
    "trigonometry": [
        "Buoc 1: Nhan dien dinh ly hoac he thuc luong giac can su dung.",
        "Buoc 2: Xac dinh cac yeu to da cho: canh, goc, duong cao, ...",
        "Buoc 3: Ap dung he thuc bang cach thay cac gia tri da biet vao dung vi tri.",
        "Buoc 4: Giai bieu thuc va trinh bay ket qua o dang don gian nhat.",
    ],
    "probability": [
        "Buoc 1: Xac dinh khong gian mau va cac bien co lien quan.",
        "Buoc 2: Ap dung cong thuc xac suat phu hop (co dien, dieu kien, Bayes).",
        "Buoc 3: Tinh so ket qua thuan loi va tong so ket qua co the.",
        "Buoc 4: Rut ra xac suat cuoi cung va doi chieu voi truc giac.",
    ],
    "linear_algebra": [
        "Buoc 1: Ghi ro ma tran/vector can xu ly va kich thuoc cua chung.",
        "Buoc 2: Ap dung phep toan ma tran thich hop (nhan, nghich dao, dinh thuc, ...).",
        "Buoc 3: Tinh toan tung buoc va ghi ro hang so trung gian.",
        "Buoc 4: Kiem tra hang/dieu kien va viet ket qua duoi dang ma tran/vector.",
    ],
}


def _diversified_agent3_fallback_lines(math_type: str, example_idx: int = 0):
    """FIX A: Return a diversified fallback block (list of strings) for
    agent3 rows whose source template has no `steps`. Picks a template
    from a math-type-specific pool if available, otherwise rotates
    through the generic default pool. `example_idx` (already passed in
    convert_entry) seeds the rotation so the same source row always
    maps to the same template -- this keeps the dataset stable across
    regenerations.
    """
    key = (math_type or "default").lower().replace(" ", "_")
    pool = _AGENT3_FALLBACK_POOL.get(key) or _AGENT3_FALLBACK_POOL["default"]
    idx = abs(hash(f"{key}:{example_idx}")) % len(pool)
    # Return the chosen template as 4 lines (so the agent3 reasoning text
    # has roughly the same length as the original 4-step reasoning).
    chosen = pool[idx]
    # If the template is a single string with embedded \n, split it.
    if "\n" in chosen:
        return chosen.split("\n")
    return [chosen]


# ============================================================
# FIX G: Substitute Vietnamese placeholders INSIDE LaTeX blocks
# ============================================================
# In agent3/agent4/agent5 generated text, raw entries contain Vietnamese
# placeholders like `một`, `bi`, `trái`, `phải` inside $...$ / $$...$$
# blocks (these were meant to be substituted with `a`, `b`, `\left(`,
# `\right)` but never were). Outside LaTeX those words are normal
# Vietnamese (e.g. "một cách", "hai bước") and MUST be preserved.
#
# We use a non-greedy regex matching $...$ and $$...$$ and only replace
# the placeholder words within the captured group. Note: `trái`/`phải`
# are NOT followed by anything in the template strings (no \b boundary
# works cleanly for Vietnamese) so we use plain string replace inside
# the matched group only. To avoid touching `một` inside a longer
# alphanumeric token (e.g. `một2` doesn't exist here but be safe) we
# still match on word boundaries for `một`/`hai`/`ba`/`bi`.

_LATEX_BLOCK_RE = re.compile(r"(\$\$?)([^$]+?)\1")
_FIX_G_MAP = [
    ("một", "a"),
    ("hai", "b"),
    ("ba", "c"),
    ("bi", "b"),
    ("trái", "\\left("),
    ("phải", "\\right)"),
]
_FIX_G_WORD_RE = re.compile(r"\b(một|hai|ba|bi)\b")
# `trái` / `phải` literally mean "left" / "right" in Vietnamese and are
# used as bracket markers. The original templates embed them as
# `\trái( ... \phải)` — i.e. with a literal `(` / `)` immediately
# after the Vietnamese word. The intended LaTeX output is
# `\left( ... \right)` (the literal `(` / `)` are absorbed by the
# `\left(` / `\right)` commands). So we substitute the two-word pair
# before falling back to the simple word-boundary mapping.
_FIX_G_PAIR_RE = re.compile(r"\\trái\(\s*|\\phải\)")


def substitute_vietnamese_in_latex(text: str) -> str:
    """FIX G: Replace Vietnamese placeholders inside `$...$` and `$$...$$`
    LaTeX blocks only. Vietnamese text outside LaTeX is preserved
    untouched. The substitution map is:
        một -> a, hai -> b, ba -> c, bi -> b,
        trái( -> \\left(, phải) -> \\right)
    Whole-word matching for `một|hai|ba|bi` (so we don't accidentally
    edit unrelated Vietnamese text inside the LaTeX group), and a
    pattern-based replace for `\\trái(` / `\\phải)` because they are
    used as bracket markers — the literal `(`/`)` immediately after
    the word is absorbed into `\\left(` / `\\right)`.
    """
    def _repl(match: "re.Match[str]") -> str:
        prefix, body = match.group(1), match.group(2)
        # 1) Vietnamese bracket markers (`\trái(` / `\phải)`) — these
        #    are always preceded by a backslash in the templates.
        new_body = _FIX_G_PAIR_RE.sub(
            lambda m: "\\left(" if m.group(0).startswith("\\tr") else "\\right)",
            body,
        )
        # 2) Whole-word replacement for short placeholders.
        new_body = _FIX_G_WORD_RE.sub(
            lambda m: {"một": "a", "hai": "b", "ba": "c", "bi": "b"}[m.group(0)],
            new_body,
        )
        return prefix + new_body + prefix

    return _LATEX_BLOCK_RE.sub(_repl, text)


# ============================================================
# Convert datasheet entry to 5-agent data
# ============================================================

def convert_entry(entry: Dict, example_idx: int = 0) -> Dict:
    """Chuyen mot entry tu datasheet.json thanh data cho 5 agents."""

    entry_id = entry.get("id", "unknown")
    instruction = entry.get("instruction", "")
    input_text = entry.get("input", "")
    steps = entry.get("steps", [])
    output = entry.get("output", "")
    canonical = entry.get("canonical_form", output)
    reasoning = entry.get("reasoning", "")
    difficulty = entry.get("difficulty", "medium")
    math_type = entry.get("type", "algebra")
    constraints = entry.get("constraints", [])
    example_problems = entry.get("example_problems", [])
    negative_examples = entry.get("negative_examples", [])
    variables = entry.get("variables", {})

    # Tao suy luan chat luong cao tu steps + examples
    thinking = []

    # Start with the actual reasoning context
    thinking.append(f"Phan tich bai toan: {instruction}")
    thinking.append(f"Dau vao can xu ly: {input_text}")
    if constraints:
        thinking.append(f"Dieu kien rang buoc: {', '.join(constraints)}")

    # Include each step with brief explanation
    if steps:
        for i, step in enumerate(steps, 1):
            clean_step = step
            for j in range(1, 20):
                clean_step = clean_step.replace(f"Bước {j}: ", "")
                clean_step = clean_step.replace(f"Buoc {j}: ", "")
                clean_step = clean_step.replace(f"Bước {j}:", "")
                clean_step = clean_step.replace(f"Buoc {j}:", "")
            thinking.append(f"Buoc {i}: {clean_step}")
    else:
        # FIX A: when the template has no steps, inject a diversified
        # reasoning block keyed on math_type so the agent3 target is not
        # the same paragraph repeated for every row (this is the source
        # of the 65.5% mode-collapse on agent3 in 5agent_expanded).
        for line in _diversified_agent3_fallback_lines(math_type, example_idx):
            thinking.append(line)

    # Add canonical form
    thinking.append(f"Ket qua dang chuan: ${canonical}$")

    reasoning_text = "\n".join(thinking)

    # FIX G: substitute Vietnamese placeholders inside LaTeX blocks.
    # `canonical` can leak `một`/`bi`/`trái`/`phải` (e.g.
    # "$\trái(2-x^2\phải) \cos x + 2 x \sin x$"). Because canonical is
    # embedded in `$...$` (inline math) AND `\boxed{...}` (LaTeX command)
    # across the agent outputs, we substitute it once on a synthetic
    # `$$...$$` wrapper so every LaTeX occurrence is cleaned up. The
    # helper is then also applied to `reasoning_text` (which contains
    # its own `${canonical}$` block) and to `boxed_answer` (a LaTeX
    # command, so we wrap it in `$...$` for the substitution pass and
    # then unwrap to keep the original `\boxed{...}` form). Outside
    # LaTeX (e.g. "một cách", "hai bước") the helper leaves Vietnamese
    # text untouched.
    canonical = substitute_vietnamese_in_latex(f"$${canonical}$$")
    if canonical.startswith("$$") and canonical.endswith("$$"):
        canonical = canonical[2:-2]
    # FIX G: also clean up `input_text` (used in agent1's `${input_text}$`
    # block) — the same placeholder leak can happen there.
    input_text = substitute_vietnamese_in_latex(f"${input_text}$")
    if input_text.startswith("$") and input_text.endswith("$"):
        input_text = input_text[1:-1]

    # Format problem text
    problem_text = f"{instruction}\nDau vao: {input_text}"

    # Format answer voi boxed
    reasoning_text = substitute_vietnamese_in_latex(reasoning_text)
    boxed_answer_raw = f"\\boxed{{{canonical}}}"
    boxed_answer = substitute_vietnamese_in_latex(f"${boxed_answer_raw}$")
    if boxed_answer.startswith("$") and boxed_answer.endswith("$"):
        boxed_answer = boxed_answer[1:-1]
    example = example_problems[example_idx] if example_problems else {}
    example_solution = example.get("solution", "") if example else ""
    example_output = example.get("output", "") if example else ""
    example_input_vals = example.get("input_values", {}) if example else {}

    # Lay vi du cu the
    # Tra ve dict data cho 5 agents
    return {
        "agent1": {
            "id": f"{entry_id}_norm",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPTS["agent1"]},
                {"role": "user", "content": f"Chuan hoa bai toan:\n\n{problem_text}"},
                {"role": "assistant", "content": f"Menh de goc: {instruction}\nKy hieu toan hoc: ${input_text}$\nBien so: {', '.join(variables.keys()) if variables else 'khong ro'}\nDang chuan mong doi: ${canonical}$\nDieu kien: {', '.join(constraints) if constraints else 'khong co'}"}
            ]
        },
        "agent2": {
            "id": f"{entry_id}_class",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPTS["agent2"]},
                {"role": "user", "content": f"Phan loai bai toan:\n\n{problem_text}"},
                {"role": "assistant", "content": f"Linh vu toan hoc: {math_type}\nMuc do kho: {difficulty}\nDac trung bai toan: {instruction}\nDang bieu thuc: ky hieu toan hoc LaTeX\nPhuong phap giai: ap dung quy tac bieu thuc dac thu\nRang buoc ky thuat: {', '.join(constraints) if constraints else 'khong co'}"}
            ]
        },
        "agent3": {
            "id": f"{entry_id}_reason",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPTS["agent3"]},
                {"role": "user", "content": f"Suy luan chi tiet tung buoc:\n\n{problem_text}"},
                {"role": "assistant", "content": reasoning_text}
            ]
        },
        "agent4": {
            "id": f"{entry_id}_solve",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPTS["agent4"]},
                {"role": "user", "content": f"Trinh bay loi giai hoan chinh:\n\n{problem_text}"},
                {"role": "assistant", "content": f"""Tom tat bai toan: {instruction}

Cong thuc chinh can tim: ${canonical}$

Loi giai chi tiet:
{reasoning_text}

Vi du cu the de kiem tra:
{example_solution if example_solution else 'Khong co vi du cu the, suy luan tu cong thuc tong quat.'}

Sai lam can tranh:
{chr(10).join([f"- {neg}" for neg in negative_examples[:3]]) if negative_examples else '- Khong co sai lam dien hinh'}

Dap an cuoi cung: {boxed_answer}"""}
            ]
        },
        "agent5": {
            "id": f"{entry_id}_verify",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPTS["agent5"]},
                {"role": "user", "content": f"Kiem tra dap an bai toan:\n\nBai toan: {problem_text}\nDap an can xac minh: {boxed_answer}"},
                {"role": "assistant", "content": f"Kiem tra: PASS\nCong thuc cuoi: ${canonical}$\nDap an xac minh: {boxed_answer}\nDanh gia: Loi giai hop le, cac buoc dien ra logic, dang chuan dat yeu cau.\nVi du kiem chung: {example_solution if example_solution else 'Khong co vi du cu the.'}"}
            ]
        }
    }


def add_example_variant(agent_data: Dict, entry: Dict, example: Dict) -> Dict:
    """Tao them sample tu vi du cu the (voi so)."""
    
    entry_id = entry.get("id", "unknown")
    instruction = entry.get("instruction", "")
    
    if not example:
        return agent_data

    input_vals = example.get("input_values", {})
    example_output = example.get("output", "")
    example_solution = example.get("solution", "")

    # Tao cau hoi voi so cu the
    input_desc = ", ".join([f"{k}={v}" for k, v in input_vals.items()])
    concrete_problem = f"{instruction}\nVoi: {input_desc}"

    # FIX G: substitute Vietnamese placeholders inside LaTeX blocks in
    # example output/solution too (they can leak `một`/`trái`/...).
    example_output = substitute_vietnamese_in_latex(f"$${example_output}$$")
    if example_output.startswith("$$") and example_output.endswith("$$"):
        example_output = example_output[2:-2]
    example_solution = substitute_vietnamese_in_latex(example_solution)

    boxed = f"\\boxed{{{example_output}}}"
    
    # Chi update agent4 (loi giai cu the)
    new_agent4 = {
        "id": f"{entry_id}_example",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["agent4"]},
            {"role": "user", "content": f"Giai bai toan cu the:\n\n{concrete_problem}"},
            {"role": "assistant", "content": f"""Tom tat: {instruction}

Loi giai:
{example_solution}

Dap an: {boxed}"""}
        ]
    }
    
    agent_data["agent4"] = new_agent4
    return agent_data


# ============================================================
# Main processing
# ============================================================

# ============================================================
# FIX G helpers (verification + in-place regen of 5agent_final/)
# ============================================================
_FIX_G_PLACEHOLDERS = ("một", "bi", "trái", "phải")


def _count_placeholder_rows(jsonl_path: str):
    """Return (total_rows, placeholder_rows) for the given jsonl file.

    A row counts as a "placeholder leak" when any of
    `một|bi|trái|phải` appears inside a `$...$` / `$$...$$` LaTeX block
    in the **last (assistant) message** of the row.
    """
    total = 0
    leaks = 0
    if not os.path.exists(jsonl_path):
        return 0, 0
    with open(jsonl_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                rec = json.loads(line)
                asst = rec["messages"][-1]["content"]
            except Exception:
                continue
            for m in _LATEX_BLOCK_RE.finditer(asst):
                body = m.group(2)
                for ph in _FIX_G_PLACEHOLDERS:
                    if ph in body:
                        leaks += 1
                        break
                else:
                    continue
                break
    return total, leaks


def _verify_fix_g():
    """Print baseline / post-fix placeholder counts for the canonical
    agent3 train file. Called twice from __main__ — once before regen
    (so we know how many leaks the existing dataset has) and once after.
    """
    print("=" * 60)
    print("FIX G verification — placeholder leak in LaTeX")
    print("=" * 60)
    for folder in ("DATA/5agent_expanded", "DATA/5agent_final"):
        for split in ("train", "val", "test"):
            path = os.path.join(folder, split, "agent3.jsonl")
            total, leaks = _count_placeholder_rows(path)
            pct = (leaks / total * 100) if total else 0.0
            print(f"   {path:<48} total={total:>4}  leaks={leaks:>4}  ({pct:5.2f}%)")
    print()


def _regen_final_with_fix_g():
    """Walk DATA/5agent_final/{train,val,test}/agent{1..5}.jsonl and
    apply `substitute_vietnamese_in_latex` to every assistant message
    in place. Writes back to the same path.

    We only touch assistant messages so the system prompt (which contains
    plain Vietnamese like "một cách", "hai bước") is preserved verbatim.
    """
    base = "DATA/5agent_final"
    if not os.path.isdir(base):
        print(f"[FIX G regen] {base} not found — skipping.")
        return
    print("=" * 60)
    print("FIX G regen — applying substitute_vietnamese_in_latex to")
    print("DATA/5agent_final/ in place")
    print("=" * 60)
    total_files = 0
    total_rows = 0
    for split in ("train", "val", "test"):
        split_dir = os.path.join(base, split)
        if not os.path.isdir(split_dir):
            continue
        for agent_id in range(1, 6):
            path = os.path.join(split_dir, f"agent{agent_id}.jsonl")
            if not os.path.exists(path):
                continue
            rows = []
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    msgs = rec.get("messages", [])
                    for msg in msgs:
                        if msg.get("role") == "assistant":
                            msg["content"] = substitute_vietnamese_in_latex(
                                msg.get("content", "")
                            )
                    rows.append(rec)
            with open(path, "w", encoding="utf-8") as fh:
                for rec in rows:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total_files += 1
            total_rows += len(rows)
            print(f"   [regen] {path}: {len(rows)} rows")
    print(f"\n   total files touched: {total_files}  rows: {total_rows}")
    print()


def process_datasheet(input_path: str, output_dir: str, val_ratio: float = 0.2, seed: int = 42):
    """
    Doc datasheet.json va tao 5 agent training files.
    
    Args:
        input_path: Duong dan den datasheet.json
        output_dir: Thu muc chua file train/val
        val_ratio: Ti le validation (mac dinh 20%)
        seed: Random seed de reproducible
    """
    
    print("=" * 60)
    print("PROCESSING DATASHEET TO 5-AGENT TRAINING DATA")
    print("=" * 60)
    
    # Load data
    print(f"\n[1/5] Loading: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        entries = json.load(f)
    print(f"   Loaded {len(entries)} entries")
    
    # Initialize data collectors
    random.seed(seed)
    
    all_data = {f"agent{i}": [] for i in range(1, 6)}
    
    # Count by type
    type_counts = {}
    
    print("\n[2/5] Converting entries...")
    
    for idx, entry in enumerate(entries):
        math_type = entry.get("type", "unknown")
        type_counts[math_type] = type_counts.get(math_type, 0) + 1
        
        # Convert entry
        agent_data = convert_entry(entry)
        
        # Add to each agent
        for agent_id, sample in agent_data.items():
            all_data[agent_id].append(sample)
        
        # Add example variant for some entries
        example_problems = entry.get("example_problems", [])
        if example_problems:
            agent_data_ex = convert_entry(entry)
            agent_data_ex = add_example_variant(agent_data_ex, entry, example_problems[0])
            for agent_id, sample in agent_data_ex.items():
                if agent_id == "agent4":  # Chi them vi du cho agent4
                    all_data[agent_id].append(sample)
        
        if (idx + 1) % 200 == 0:
            print(f"   Processed {idx + 1}/{len(entries)} entries...")
    
    print(f"\n   Type distribution:")
    for t, c in sorted(type_counts.items()):
        print(f"      - {t}: {c}")
    
    # Shuffle and split
    print("\n[3/5] Shuffling and splitting train/val...")
    
    split_data = {}
    for agent_id, samples in all_data.items():
        random.shuffle(samples)
        
        val_size = int(len(samples) * val_ratio)
        train_samples = samples[:-val_size] if val_size > 0 else samples
        val_samples = samples[-val_size:] if val_size > 0 else []
        
        split_data[agent_id] = {
            "train": train_samples,
            "val": val_samples
        }
        
        print(f"   {agent_id}: {len(samples)} total | train: {len(train_samples)} | val: {len(val_samples)}")
    
    # Save files
    print("\n[4/5] Saving files...")
    os.makedirs(output_dir, exist_ok=True)
    
    for agent_id in sorted(split_data.keys()):
        # Save train
        train_path = os.path.join(output_dir, f"{agent_id}_train.jsonl")
        with open(train_path, 'w', encoding='utf-8') as f:
            for sample in split_data[agent_id]["train"]:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        # Save val
        val_path = os.path.join(output_dir, f"{agent_id}_val.jsonl")
        with open(val_path, 'w', encoding='utf-8') as f:
            for sample in split_data[agent_id]["val"]:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        print(f"   [OK] {agent_id}: train={len(split_data[agent_id]['train'])}, val={len(split_data[agent_id]['val'])}")
    
    # Summary
    print("\n[5/5] Summary:")
    print(f"   Output: {output_dir}")
    total_train = sum(len(v["train"]) for v in split_data.values())
    total_val = sum(len(v["val"]) for v in split_data.values())
    print(f"   Total samples: train={total_train}, val={total_val}")
    
    # File sizes
    print("\n   Files created:")
    for f in sorted(os.listdir(output_dir)):
        fpath = os.path.join(output_dir, f)
        size_kb = os.path.getsize(fpath) / 1024
        print(f"      - {f}: {size_kb:.1f} KB")
    
    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
    
    return split_data


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # ============================================================
    # FIX G: verification + regen of 5agent_final/ in place
    # ============================================================
    # Step 1: baseline count of placeholder-leak rows in agent3 train.
    _verify_fix_g()

    # Step 2: apply Fix G substitution to every message of every agent
    # file under DATA/5agent_final/ (in place). This surgically patches
    # the existing dataset without regenerating from raw data, so it
    # also picks up content produced by scripts/transform_for_5agent.py
    # which we do not modify here.
    _regen_final_with_fix_g()

    # Step 3: re-count after regen.
    _verify_fix_g()

    # ============================================================
    # Original datasheet → 5-agent dataset generation
    # ============================================================
    # Config
    INPUT_PATH = "DATA/datasheet.json"
    OUTPUT_DIR = "DATA/5agent_dataset_full"
    VAL_RATIO = 0.2  # 20% for validation
    SEED = 42

    print(f"\nConfig:")
    print(f"   Input:  {INPUT_PATH}")
    print(f"   Output: {OUTPUT_DIR}")
    print(f"   Val ratio: {VAL_RATIO}")
    print(f"   Seed: {SEED}")

    process_datasheet(INPUT_PATH, OUTPUT_DIR, VAL_RATIO, SEED)
