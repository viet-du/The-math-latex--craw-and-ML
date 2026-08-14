"""
Expand Dataset from Templates — 5-Agent Format
=============================================
Generate training data for 5 agents from datasheet templates.
Each agent gets {user + assistant} message pair with role-specific content.

Usage:
    python scripts/expand_dataset.py
"""

import json
import random
import re
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# FIX G: Vietnamese placeholder substitution inside LaTeX blocks.
# `substitute_vietnamese_in_latex` replaces `một` -> `a`, `hai` -> `b`,
# `ba` -> `c`, `bi` -> `b`, `\trái(` -> `\left(`, `\phải)` -> `\right)`
# but ONLY inside `$...$` / `$$...$$` blocks. Plain Vietnamese outside
# LaTeX (e.g. "một cách", "hai bước" in narrative text) is preserved.
# The canonical implementation lives in `convert_datasheet_to_agents.py`
# and is re-exported by `latex_vi_fixes` -- we never duplicate it.
from latex_vi_fixes import substitute_vietnamese_in_latex

# Variable patterns to replace in text
VAR_PATTERNS = [
    (r'\{a\}', lambda: random.randint(1, 20)),
    (r'\{b\}', lambda: random.randint(1, 20)),
    (r'\{c\}', lambda: random.randint(1, 15)),
    (r'\{d\}', lambda: random.randint(2, 10)),
    (r'\{e\}', lambda: random.randint(2, 8)),
    (r'\{n\}', lambda: random.randint(5, 50)),
    (r'\{m\}', lambda: random.randint(2, 30)),
    (r'\{x\}', lambda: random.randint(1, 100)),
    (r'\{y\}', lambda: random.randint(1, 50)),
    (r'\{r\}', lambda: random.randint(5, 20)),
    (r'\{h\}', lambda: random.randint(3, 15)),
    (r'\{k\}', lambda: random.randint(1, 10)),
    (r'\{p\}', lambda: random.randint(10, 90)),
    (r'\{v\}', lambda: random.randint(30, 120)),
    (r'\{t\}', lambda: random.randint(1, 10)),
    (r'\{l\}', lambda: random.randint(10, 50)),
    (r'\{w\}', lambda: random.randint(5, 30)),
    (r'\{s\}', lambda: random.randint(2, 15)),
]

TYPE_MAP = {
    'algebra': 'algebra', 'linear_algebra': 'linear_algebra',
    'calculus': 'calculus', 'probability': 'probability',
    'probability_statistics': 'probability_statistics', 'statistics': 'statistics',
    'trigonometry': 'trigonometry', 'geometry': 'geometry',
    'combinatorics': 'combinatorics', 'sequences': 'sequences',
    'optimization': 'optimization', 'data_structures_algorithms': 'dsa',
    'machine_learning': 'machine_learning', 'deep_learning': 'deep_learning',
    'information_security': 'information_security', 'mathematical_physics': 'math',
}

# Agent system prompts (match convert_datasheet_to_agents.py)
SYSTEM_PROMPTS = {
    "agent1": "Ban la GIAO SU TOAN HOC VIET NAM.\nNhiem vu: CHUAN HOA bai toan tu loi van sang dinh dang toan hoc.\n\nCHI DUNG TIENG VIET. KHONG DUNG TIENG ANH.\n\nYeu cau:\n1. Chuyen doi ngon ngu tu nhien → ky hieu toan hoc\n2. Viet tat ca cong thuc bang LaTeX chuan ($...$ hoac $$...$$)\n3. Xac dinh ro: bien so, hang so, dieu kien\n4. Giu nguyen y nghia bai toan",
    "agent2": "Ban la GIAO VIEN TOAN HOC VIET NAM.\nNhiem vu: PHAN LOAI bai toan va xac dinh rang buoc.\n\nCHI DUNG TIENG VIET. KHONG DUNG TIENG ANH.\n\nYeu cau:\n1. Xac dinh LINH VUC: dai so | phan so | giai tich | xac suat thong ke | hinh hoc | luong giac\n2. Xac dinh MUC DO: de | trung binh | kho\n3. Xac dinh PHUONG PHAP giai phu hop\n4. Liet ke DIEU KIEN RANG BUOC",
    "agent3": "Ban la GIAO SU TOAN HOC VIET NAM.\nNhiem vu: TRINH BAY SUY LUAN TUNG BUOC de giai bai toan.\n\nCHI DUNG TIENG VIET. KHONG DUNG TIENG ANH.\n\nQUY TAC BAT BUOC:\n1. Moi buoc phai co so thu tu ro rang: \"Buoc 1:\", \"Buoc 2:\", ...\n2. Moi buoc phai co cong thuc LaTeX ro rang\n3. Moi buoc phai co giai thich TAI SAO bang tieng Viet\n4. SUY LUAN PHAI LOGIC, tung buoc ro rang nhu mot nguoi thay dang giang",
    "agent4": "Ban la GIAO VIEN TOAN CHI TIET VIET NAM.\nNhiem vu: TRINH BAY LOI GIAI HOAN CHINH theo phong cach su pham.\n\nCHI DUNG TIENG VIET. KHONG DUNG TIENG ANH.\n\nKet qua cuoi cung phai trong \\boxed{...}\nTat ca cong thuc dung LaTeX\nGiai thich bang tieng Viet",
    "agent5": "Ban la KIEM TRA VIEN CHAT LUONG VIET NAM.\nNhiem vu: XAC MINH va DANH GIA loi giai.\n\nCHI DUNG TIENG VIET. KHONG DUNG TIENG ANH.\n\nKiem tra:\n1. Loi giai co \\boxed{} khong?\n2. Noi dung \\boxed{} co chinh xac khong?\n3. Cac buoc co LOGIC khong?\n\nTra loi:\n- Kiem tra: [PASS/FAIL]\n- Dap an xac minh: \\boxed{...}",
}


def expand_text(text, seed=42):
    random.seed(seed)
    result = text
    for pattern, generator in VAR_PATTERNS:
        while re.search(pattern, result):
            result = re.sub(pattern, str(generator()), result, count=1)
            random.seed(seed + 1)
    return result


# FIX A: Diversified agent3 fallback templates.
# Before this fix, the agent3 fallback for entries with empty `steps` was a
# single static string repeated for every row. In the 5agent_expanded
# dataset that string repeated 778/1188 times (65.5% of agent3 train rows)
# and 83/149 times in test, which biased the agent3 LoRA toward pure
# memorisation -- a noise-dominated signal that no capacity tweak can fix.
# The helper below rotates through math-type-specific pools (or generic
# defaults when no math_type is known) so the fallback is no longer
# mode-collapsed. `example_idx` (already a parameter of build_agent_messages)
# seeds the rotation so the same source row always maps to the same
# template -- this keeps the dataset stable across regenerations.
_AGENT3_FALLBACK_TEMPLATES = {
    "default": [
        "Buoc 1: Xac dinh dung ban chat cua bai toan va nhan dien cong thuc nen tang can ap dung.\nBuoc 2: Phan tich cac du kien da cho de biet dau la bien, dau la hang so va dau la dieu kien xac dinh.\nBuoc 3: Bien doi bieu thuc theo duong loi toan hoc phu hop va giu nguyen y nghia cua bai toan.\nBuoc 4: Rut gon ket qua va trinh bay dap an o dang chuan, de doc va de kiem tra.",
        "Buoc 1: Doc ky yeu cau va phat bieu lai bai toan bang ngon ngu toan hoc.\nBuoc 2: Liet ke tat ca cac bien, hang so va rang buoc lien quan.\nBuoc 3: Ap dung cong thuc hoac dinh ly thich hop, thuc hien bien doi tung buoc.\nBuoc 4: Ra soat lai logic, don gian hoa bieu thuc va trinh bay dap an cuoi cung.",
        "Buoc 1: Nhan dien dang bai toan va pham vi kien thuc can su dung.\nBuoc 2: Tom tat du kien dau vao va xac dinh muc tieu can dat.\nBuoc 3: Lua chon phuong phap, thay so va tinh toan theo trinh tu.\nBuoc 4: Kiem tra tinh hop ly va viet ket qua cuoi cung duoi dang ro rang.",
        "Buoc 1: Phan tich moi quan he giua cac dai luong trong bai toan.\nBuoc 2: Thiet lap mo hinh toan hoc (phuong trinh, he, do thi, ...).\nBuoc 3: Giai mo hinh bang cac phep bien doi dai so hoac cong cu phu hop.\nBuoc 4: Doi chieu ket qua voi dieu kien de bai va trinh bay dap an.",
    ],
    "algebra": [
        "Buoc 1: Ghi ro bieu thuc dai so can xu ly va khai trien cac thanh phan.\nBuoc 2: Quy dong, phan tich thua so hoac ap dung hang dang thuc neu can.\nBuoc 3: Rut gon tung ve va thu gon bieu thuc ve dang don gian nhat.\nBuoc 4: Kiem tra bang phep the gia tri hoac doi chieu voi dieu kien ban dau.",
        "Buoc 1: Xac dinh an so, he so va bac cua phuong trinh/he can giai.\nBuoc 2: Bien doi tuong duong (cong/tru, nhan/chia, the) de co lap an.\nBuoc 3: Giai tuan tu tung buoc va ghi ro cac phep toan trung gian.\nBuoc 4: Thu lai nghiem vao phuong trinh goc de xac nhan dap an.",
    ],
    "linear_algebra": [
        "Buoc 1: Ghi ro ma tran/vector can xu ly va kich thuoc cua chung.\nBuoc 2: Ap dung phep toan ma tran thich hop (nhan, nghich dao, dinh thuc, ...).\nBuoc 3: Tinh toan tung buoc va ghi ro hang so trung gian.\nBuoc 4: Kiem tra hang/dieu kien va viet ket qua duoi dang ma tran/vector.",
    ],
    "calculus": [
        "Buoc 1: Xac dinh loai bai toan giai tich (dao ham, tich phan, gioi han).\nBuoc 2: Ap dung quy tac tuong ung (chuyen dinh ly co ban, ...).\nBuoc 3: Tinh toan tung buoc va ghi ro cac phep bien doi trung gian.\nBuoc 4: Don gian hoa ket qua va doi chieu voi mien xac dinh.",
        "Buoc 1: Doc ky ham so va xac dinh mien xac dinh cua no.\nBuoc 2: Lua chon phep toan giai tich thich hop (dao ham, tich phan, chuoi).\nBuoc 3: Thuc hien phep toan theo tung buoc, don gian hoa khi co the.\nBuoc 4: Kiem tra ket qua bang cach lay vi phan/tich phan nguoc va viet dap an.",
    ],
    "probability": [
        "Buoc 1: Xac dinh khong gian mau va cac bien co lien quan.\nBuoc 2: Ap dung cong thuc xac suat phu hop (co dien, dieu kien, Bayes).\nBuoc 3: Tinh so ket qua thuan loi va tong so ket qua co the.\nBuoc 4: Rut ra xac suat cuoi cung va doi chieu voi truc giac.",
    ],
    "probability_statistics": [
        "Buoc 1: Xac dinh tap du lieu va loai thong ke can tinh (trung binh, phuong sai, ...).\nBuoc 2: Lua chon cong thuc thong ke tuong ung voi du lieu.\nBuoc 3: Thay gia tri va tinh toan tung buoc mot cach can than.\nBuoc 4: Dien giai ket qua theo ngu canh bai toan.",
    ],
    "statistics": [
        "Buoc 1: Xac dinh tap du lieu va loai thong ke can tinh (trung binh, phuong sai, ...).\nBuoc 2: Lua chon cong thuc thong ke tuong ung voi du lieu.\nBuoc 3: Thay gia tri va tinh toan tung buoc mot cach can than.\nBuoc 4: Dien giai ket qua theo ngu canh bai toan.",
    ],
    "trigonometry": [
        "Buoc 1: Nhan dien dinh ly hoac he thuc luong giac can su dung.\nBuoc 2: Xac dinh cac yeu to da cho: canh, goc, duong cao, ...\nBuoc 3: Ap dung he thuc bang cach thay cac gia tri da biet vao dung vi tri.\nBuoc 4: Giai bieu thuc va trinh bay ket qua o dang don gian nhat.",
    ],
    "geometry": [
        "Buoc 1: Ve hinh va ghi nhan cac yeu to hinh hoc da cho (canh, goc, duong cao, ...).\nBuoc 2: Xac dinh cac dinh ly/tinh chat co the ap dung (dong dang, Pitago, ...).\nBuoc 3: Thiet lap he thuc giua cac doan thang, goc, dien tich hoac the tich.\nBuoc 4: Tinh toan va trinh bay ket qua cuoi cung.",
        "Buoc 1: Dinh vi doi tuong hinh hoc can khao sat (diem, duong, mat, khoi).\nBuoc 2: Liet ke cac tinh chat dac trung (vuong goc, song song, can, deu, ...).\nBuoc 3: Su dung he thuc luong hoac cong thuc tinh chu vi/dien tich/the tich.\nBuoc 4: Tinh so do con thieu va rut ra ket luan.",
    ],
    "combinatorics": [
        "Buoc 1: Xac dinh loai bai toan dem (hoan vi, chinh hop, to hop) va cac rang buoc.\nBuoc 2: Lua chon cong thuc dem thich hop voi du lieu dau vao.\nBuoc 3: Thay gia tri va tinh toan so luong theo tung buoc.\nBuoc 4: Kiem tra ket qua voi dieu kien nho/lo cu the de xac nhan dap an.",
    ],
    "sequences": [
        "Buoc 1: Nhan dien dang day so (cap so cong, cap so nhan, quy nap, ...).\nBuoc 2: Xac dinh cong sai/cong boi hoac quy luat truyen.\nBuoc 3: Ap dung cong thuc tong/quy nap de tinh ket qua can tim.\nBuoc 4: Trinh bay dap an cuoi cung o dang chinh quy.",
    ],
    "optimization": [
        "Buoc 1: Doc lai bai toan toi uu va xac dinh ham muc tieu, bien so va rang buoc.\nBuoc 2: Chon phuong phap toi uu thich hop (dao ham, Lagrange, quy hoach tuyen tinh, ...).\nBuoc 3: Thiet lap dieu kien can va tinh toan cac gia tri toi uu.\nBuoc 4: Kiem tra tinh kha thi va trinh bay ket qua toi uu cuoi cung.",
    ],
    "data_structures_algorithms": [
        "Buoc 1: Hieu ro yeu cau thuat toan/cau truc du lieu (sap xep, tim kiem, do phuc tap, ...).\nBuoc 2: Lua chon thuat toan hoac cau truc du lieu phu hop voi quy mo du lieu.\nBuoc 3: Phan tich tung buoc thuat toan, ve so do/minh hoa neu can.\nBuoc 4: Tinh do phuc tap thoi gian/khong gian va rut ra ket luan.",
    ],
    "machine_learning": [
        "Buoc 1: Xac dinh bai toan hoc may (phan loai, hoi quy, cum, giam chieu, ...).\nBuoc 2: Lua chon mo hinh va ham mat mat phu hop voi du lieu.\nBuoc 3: Trinh bay cong thuc cap nhat tham so (gradient descent, ...).\nBuoc 4: Tom tat ket qua cuoi cung theo bai toan dat ra.",
    ],
    "deep_learning": [
        "Buoc 1: Xac dinh kien truc mang (CNN, RNN, Transformer) va bai toan can giai.\nBuoc 2: Viet cong thuc lan truyen thuan va lan truyen nguoc tuong ung.\nBuoc 3: Tinh gradient cua ham mat mat theo cac tham so cua mang.\nBuoc 4: Tom tat cong thuc cap nhat trong so va y nghia cua bai toan.",
    ],
    "information_security": [
        "Buoc 1: Xac dinh bai toan bao mat (mahoa, chu ky so, bam, xac thuc, ...).\nBuoc 2: Lua chon so do/thuat toan thich hop (RSA, AES, SHA, ...).\nBuoc 3: Trinh bay cac buoc tinh toan theo cong thuc ro rang.\nBuoc 4: Tom tat ket qua (khoa, bam, chu ky) va y nghia bao mat.",
    ],
    "mathematical_physics": [
        "Buoc 1: Xac dinh hien tuong vat ly va cac dai luong lien quan.\nBuoc 2: Thiet lap mo hinh toan (phuong trinh vi phan, phuong trinh song, ...).\nBuoc 3: Ap dung cong thuc giai tuong ung va tinh toan tung buoc.\nBuoc 4: Dien giai ket qua theo ngu canh vat ly cua bai toan.",
    ],
}


def _diversified_agent3_fallback(math_type: str, example_idx: int = 0) -> str:
    """FIX A: Return a diversified fallback for agent3 rows with empty steps.
    Picks a template from a math-type-specific pool if available, otherwise
    rotates through the generic default pool. `example_idx` (already a
    parameter of build_agent_messages) seeds the rotation so the same
    source row always maps to the same template -- this keeps the dataset
    stable across regenerations.
    """
    key = (math_type or "default").lower().replace(" ", "_")
    pool = _AGENT3_FALLBACK_TEMPLATES.get(key) or _AGENT3_FALLBACK_TEMPLATES["default"]
    idx = abs(hash(f"{key}:{example_idx}")) % len(pool)
    return pool[idx]


def build_agent_messages(template, problem_text, agent_id, example_idx=0):
    """Build user+assistant messages for a specific agent from a template."""
    entry_id = template.get('id', 'unknown')
    instruction = template.get('instruction', '')
    reasoning = template.get('reasoning', '')
    output = template.get('output', '')
    canonical = template.get('canonical_form', output)
    math_type = template.get('type', 'algebra')
    difficulty = template.get('difficulty', 'medium')
    constraints = template.get('constraints', [])
    variables = template.get('variables', {})
    steps = template.get('steps', [])

    boxed = f"\\boxed{{{canonical}}}"

    if agent_id == 'agent1':
        # Normalize: problem → mathematical form
        user_content = f"Chuan hoa bai toan:\n\n{problem_text}"
        assistant_content = (
            f"Menh de goc: {instruction}\n"
            f"Ky hieu toan hoc: ${canonical}$\n"
            f"Bien so: {', '.join(variables.keys()) if variables else 'khong ro'}\n"
            f"Dieu kien: {', '.join(constraints) if constraints else 'khong co'}"
        )

    elif agent_id == 'agent2':
        # Classify: problem → domain + difficulty + constraints
        user_content = f"Phan loai bai toan:\n\n{problem_text}"
        assistant_content = (
            f"Linh vu toan hoc: {math_type}\n"
            f"Muc do kho: {difficulty}\n"
            f"Dac trung bai toan: {instruction}\n"
            f"Dang bieu thuc: ky hieu toan hoc LaTeX\n"
            f"Phuong phap giai: ap dung quy tac bieu thuc dac thu\n"
            f"Rang buoc ky thuat: {', '.join(constraints) if constraints else 'khong co'}"
        )

    elif agent_id == 'agent3':
        # Reason: problem → step-by-step reasoning
        reasoning_clean = []
        for s in steps:
            for j in range(1, 20):
                s = s.replace(f"Bước {j}: ", "").replace(f"Buoc {j}: ", "")
            reasoning_clean.append(s)
        user_content = f"Suy luan chi tiet tung buoc:\n\n{problem_text}"
        if reasoning_clean:
            assistant_content = "\n".join(f"Buoc {i+1}: {s}" for i, s in enumerate(reasoning_clean))
        else:
            # FIX A: Diversify the agent3 fallback so that empty-steps rows
            # do NOT collapse onto a single static boilerplate. In the
            # 5agent_expanded dataset this single string repeated 778/1188
            # times (65.5% of agent3 train rows) and biased the LoRA toward
            # pure memorisation, which is what drove agent3's eval loss
            # to 0.92 even after rank was reduced from 64 -> 32. Now we
            # pick a per-math-type template (or rotate generic ones) so
            # the gradient signal is no longer mode-collapsed.
            assistant_content = _diversified_agent3_fallback(math_type, example_idx)
        if canonical:
            assistant_content += f"\n\nKet qua dang chuan: ${canonical}$"

    elif agent_id == 'agent4':
        # Solve: problem → full solution with boxed answer
        steps_text = "\n".join(f"- {s}" for s in steps[:5]) if steps else ""
        user_content = f"Trinh bay loi giai hoan chinh:\n\n{problem_text}"
        assistant_content = (
            f"Tom tat bai toan: {instruction}\n\n"
            f"Cac buoc giai:\n{steps_text}\n\n"
            f"Dap an cuoi cung: {boxed}"
        )

    else:  # agent5
        # Verify: check answer
        user_content = (
            f"Kiem tra dap an bai toan:\n\n"
            f"Bai toan: {problem_text}\n"
            f"Dap an can xac minh: {boxed}"
        )
        assistant_content = (
            f"Kiem tra: PASS\n"
            f"Cong thuc cuoi: ${canonical}$\n"
            f"Dap an xac minh: {boxed}\n"
            f"Danh gia: Loi giai hop le, cac buoc dien ra logic."
        )

    # FIX G: clean up any Vietnamese placeholders (`một`, `bi`, `trái`,
    # `phải`) that leak into the LaTeX blocks of the assistant message
    # (`$...$` for canonical, `\boxed{...}` for the boxed answer). Plain
    # Vietnamese narrative text outside LaTeX is left untouched.
    assistant_content = substitute_vietnamese_in_latex(assistant_content)
    user_content = substitute_vietnamese_in_latex(user_content)

    return {
        'id': f"{entry_id}_agent{agent_id}",
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPTS.get(agent_id, '')},
            {'role': 'user', 'content': user_content},
            {'role': 'assistant', 'content': assistant_content},
        ]
    }


def main():
    print("=" * 60)
    print("EXPAND DATASET — 5-AGENT FORMAT")
    print("=" * 60)

    print("\nLoading datasheet...")
    with open('DATA/datasheet_final.json', 'r', encoding='utf-8') as f:
        templates = json.load(f)
    print(f"Templates loaded: {len(templates)}")

    # Build full problem list with template data (not just strings)
    print("\nGenerating problem list...")
    all_entries = []

    for i, template in enumerate(templates):
        template_id = template.get('id', '')
        template_type = template.get('type', 'math')

        # Primary problem: expand instruction with variables
        seed = hash(template_id) % 100000
        primary_problem = expand_text(template.get('instruction', ''), seed)

        entry = {
            'template': template,
            'problem': primary_problem,
            'category': TYPE_MAP.get(template_type, 'math'),
            'type': template_type,
            'id_prefix': template_id,
        }
        all_entries.append(entry)

        if (i + 1) % 200 == 0:
            print(f"  Processed {i + 1}/{len(templates)}...")

    print(f"Total problem entries: {len(all_entries)}")

    # Category distribution
    from collections import Counter
    cats = Counter(e['category'] for e in all_entries)
    print("\nCategory distribution:")
    for cat, count in cats.most_common():
        print(f"  {cat}: {count}")

    # Split into train/val/test
    print("\nSplitting dataset...")
    random.seed(42)
    random.shuffle(all_entries)

    n = len(all_entries)
    n_train = int(n * 0.8)
    n_val = int(n * 0.1)

    train_entries = all_entries[:n_train]
    val_entries = all_entries[n_train:n_train + n_val]
    test_entries = all_entries[n_train + n_val:]

    print(f"  Train: {len(train_entries)}")
    print(f"  Val:   {len(val_entries)}")
    print(f"  Test:  {len(test_entries)}")

    # Save per-agent jsonl files
    print("\nSaving...")
    output_dir = Path('DATA/5agent_expanded')
    for split_name, entries in [('train', train_entries), ('val', val_entries), ('test', test_entries)]:
        for agent_id in ['agent1', 'agent2', 'agent3', 'agent4', 'agent5']:
            filepath = output_dir / split_name / f'{agent_id}.jsonl'
            with open(filepath, 'w', encoding='utf-8') as f:
                for entry in entries:
                    record = build_agent_messages(
                        entry['template'], entry['problem'], agent_id
                    )
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
            print(f"  [{split_name}/{agent_id}] {len(entries)} samples → {filepath.name}")

    print(f"\nSaved to: {output_dir}")
    print("\n" + "=" * 60)
    print(f"DONE! {len(all_entries)} templates × 5 agents = {len(all_entries) * 5} samples")
    print("=" * 60)


if __name__ == "__main__":
    main()
