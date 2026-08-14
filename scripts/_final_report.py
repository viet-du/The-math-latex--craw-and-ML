"""Đánh giá cuối cùng: file sau khi fix."""
import json
import re
import sys
from collections import Counter

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

with open("DATA/datasheet_final_vi3.json", "r", encoding="utf-8") as f:
    data = json.load(f)

GENERIC_STEP_PATTERNS = [
    r"^Bước \d+: Xác định đúng bản chất",
    r"^Bước \d+: Phân tích các dữ kiện",
    r"^Bước \d+: Biến đổi biểu thức theo đường lối",
    r"^Bước \d+: Rút gọn kết quả và trình bày",
    r"^Bước \d+: Xác định đúng dạng bài toán",
    r"^Bước \d+: Nhận diện dạng hàm số",
    r"^Bước \d+: Dùng cấu trúc chuẩn",
    r"^Bước \d+: Thực hiện các phép biến đổi đại số",
    r"^Bước \d+: Trình bày kết quả ở dạng chuẩn và kiểm tra",
    r"^Bước \d+: Nhận diện đúng định lý hoặc hệ thức lượng giác",
    r"^Bước \d+: Xác định các yếu tố đã cho",
    r"^Bước \d+: Áp dụng hệ thức phù hợp",
    r"^Bước \d+: Giải biểu thức và trình bày",
    r"^Bước \d+: Xét giá trị của biểu thức",
    r"^Bước \d+: Sử dụng các kỹ thuật phù hợp",
    r"^Bước \d+: Tìm giới hạn bằng cách loại bỏ",
    r"^Bước \d+: Kết luận giá trị giới hạn\.$",
]

GENERIC_REASONING_PATTERNS = [
    r"Khi giải, ta nên bắt đầu bằng việc đọc kỹ cấu trúc biểu thức",
    r"Cách suy nghĩ đúng là nhìn thấy bản chất của bài toán",
    r"Sau khi xác định được quy tắc phù hợp, ta biến đổi theo từng bước",
    r"Trong dạng chuẩn, ta hướng tới biểu thức",
]


def is_generic_step(step):
    for pat in GENERIC_STEP_PATTERNS:
        if re.search(pat, step):
            return True
    return False


def is_generic_reasoning(reasoning):
    for pat in GENERIC_REASONING_PATTERNS:
        if re.search(pat, reasoning):
            return True
    return False


def has_generic_steps(steps):
    return any(is_generic_step(s) for s in steps)


def has_generic_reasoning(reasoning):
    return is_generic_reasoning(reasoning)


print("=" * 80)
print("ĐÁNH GIÁ CUỐI CÙNG - FILE SAU KHI FIX")
print("=" * 80)
print(f"\nTổng entries: {len(data)}")

# Đếm
generic_steps = sum(1 for e in data if has_generic_steps(e.get("steps", [])))
generic_reasoning = sum(1 for e in data if has_generic_reasoning(e.get("reasoning", "")))

print(f"\nSteps generic:    {generic_steps}/{len(data)} ({generic_steps*100/len(data):.1f}%)")
print(f"Reasoning generic: {generic_reasoning}/{len(data)} ({generic_reasoning*100/len(data):.1f}%)")

# Sample các topic
print("\n=== SAMPLE 5 ENTRIES SAU KHI FIX ===\n")
target_ids = ["alg_fraction_subtract_same_denominator", "math_calculus_chain_rule", "trig_pythagorean_identity", "calc_gamma_function", "geom_triangle_angle_sum"]
for tid in target_ids:
    for e in data:
        if e.get("id") == tid:
            print(f"\n--- ID: {tid} ---")
            print(f"Instruction: {e.get('instruction', '')}")
            print(f"Output: {e.get('output', '')}")
            print(f"Steps ({len(e.get('steps', []))}):")
            for i, s in enumerate(e.get("steps", [])):
                print(f"  [{i+1}] {s}")
            print(f"Reasoning: {e.get('reasoning', '')[:200]}...")
            break

# Steps per entry
print("\n=== Steps per entry ===")
step_counts = Counter(len(e.get("steps", [])) for e in data)
for c, n in sorted(step_counts.items()):
    print(f"  {c} steps: {n} entries")

# Output chứa LaTeX
print("\n=== Output chứa LaTeX keywords ===")
latex_kws = ["\\frac", "\\int", "\\sum", "\\sqrt", "\\sin", "\\cos", "\\log", "\\lim", "\\partial", "\\nabla"]
for kw in latex_kws:
    cnt = sum(1 for e in data if kw in e.get("output", ""))
    print(f"  {kw:12s}: {cnt} entries")