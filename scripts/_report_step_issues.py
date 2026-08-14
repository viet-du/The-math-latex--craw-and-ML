"""Tạo báo cáo phân tích steps + đề xuất sửa."""
import json
import re
import sys
from collections import defaultdict, Counter

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

SRC = r"D:\Hoc_tap\The-math-latex--craw-and-ML\DATA\datasheet_final_vi3.json"

with open(SRC, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total entries: {len(data)}")
print("=" * 80)

# ===== ISSUE 1: Steps quá generic, không đề cập khái niệm cụ thể =====
print("\n🚨 ISSUE 1: Steps quá generic - không đề cập khái niệm cụ thể")
print("=" * 80)

generic_patterns = [
    r"Xác định đúng bản chất",
    r"Phân tích các dữ kiện",
    r"Biến đổi biểu thức theo",
    r"Rút gọn kết quả và trình bày",
    r"Xác định đúng dạng",
    r"Phân biệt rõ cơ số",
    r"Phân biệt rõ giữa",
]

generic_count = 0
generic_entries = []
for idx, entry in enumerate(data):
    steps = entry.get("steps", [])
    step_text = " ".join(steps)
    is_generic = sum(1 for pat in generic_patterns if re.search(pat, step_text)) >= 2
    if is_generic:
        generic_count += 1
        generic_entries.append(idx)

print(f"Entries có steps quá generic: {generic_count}/{len(data)} ({100*generic_count/len(data):.1f}%)")

# ===== ISSUE 2: Steps không đề cập khái niệm trong instruction =====
print("\n🚨 ISSUE 2: Steps không đề cập khái niệm trong instruction")
print("=" * 80)

# Topic extraction từ instruction
topic_keywords = {
    "tích phân": ["tích phân", "nguyên hàm", "integral"],
    "đạo hàm": ["đạo hàm", "vi phân", "derivative"],
    "logarit": ["logarit", "logarithm", "ln"],
    "lượng giác": ["lượng giác", "sin", "cos", "tan", "cot", "trigonometric"],
    "đa thức": ["đa thức", "polynomial"],
    "phương trình": ["phương trình", "equation"],
    "hệ phương trình": ["hệ phương trình", "system"],
    "bất phương trình": ["bất phương trình", "inequality"],
    "hàm số": ["hàm số", "function"],
    "đồ thị": ["đồ thị", "graph", "biểu đồ"],
    "giới hạn": ["giới hạn", "limit"],
    "chu vi": ["chu vi", "perimeter"],
    "diện tích": ["diện tích", "area"],
    "thể tích": ["thể tích", "volume"],
    "xác suất": ["xác suất", "probability"],
    "thống kê": ["thống kê", "statistics"],
    "ma trận": ["ma trận", "matrix"],
    "vectơ": ["vectơ", "vector"],
    "số phức": ["số phức", "complex"],
    "khai triển": ["khai triển", "expand"],
    "phân tích": ["phân tích", "factor"],
    "rút gọn": ["rút gọn", "simplify"],
    "tổ hợp": ["tổ hợp", "combination"],
    "hoán vị": ["hoán vị", "permutation"],
    "xác suất có điều kiện": ["xác suất có điều kiện", "conditional probability"],
    "chuỗi": ["chuỗi", "series"],
    "số nguyên": ["số nguyên", "integer"],
    "số thực": ["số thực", "real"],
    "số hữu tỉ": ["số hữu tỉ", "rational"],
    "số vô tỉ": ["số vô tỉ", "irrational"],
    "phép chia": ["phép chia", "division"],
    "phép nhân": ["phép nhân", "multiplication"],
    "phép cộng": ["phép cộng", "addition"],
    "phép trừ": ["phép trừ", "subtraction"],
}

mismatch_count = 0
mismatch_examples = []
for idx, entry in enumerate(data):
    instruction = entry.get("instruction", "").lower()
    steps = entry.get("steps", [])
    step_text = " ".join(steps).lower()
    output = entry.get("output", "").lower()

    # Tìm topics in instruction
    topics_in_instruction = []
    for topic, kws in topic_keywords.items():
        for kw in kws:
            if kw in instruction:
                topics_in_instruction.append(topic)
                break

    # Check each topic có trong steps
    missing = []
    for topic in topics_in_instruction:
        kws = topic_keywords[topic]
        if not any(kw in step_text for kw in kws):
            missing.append(topic)

    if missing:
        mismatch_count += 1
        if len(mismatch_examples) < 15:
            mismatch_examples.append((idx, entry.get("id"), entry.get("instruction", "")[:100], missing))

print(f"Entries có instruction nói về topic X nhưng steps KHÔNG đề cập: {mismatch_count}/{len(data)}")
print("\nExamples:")
for idx, eid, instr, missing in mismatch_examples:
    print(f"  [{idx}] {eid}: {instr!r}")
    print(f"      Missing: {missing}")

# ===== ISSUE 3: Cùng 1 output được gắn với nhiều instruction khác nhau =====
print("\n\n🚨 ISSUE 3: Output có thể không khớp với instruction")
print("=" * 80)

disconnect_count = 0
disconnect_examples = []
for idx, entry in enumerate(data):
    output = entry.get("output", "")
    instruction = entry.get("instruction", "")
    if not output or not instruction:
        continue

    # Check if output has formula but instruction doesn't mention math
    # Check if instruction mentions specific phi/phép but output has different
    # Check if instruction has specific function but output has different
    instr_l = instruction.lower()
    output_l = output.lower()

    issues = []

    # Instruction mentions "logarit" but output has no log
    if ("logarit" in instr_l or "logarithm" in instr_l) and "log" not in output_l and "\\ln" not in output_l:
        issues.append("instruction nói về logarith nhưng output không có log")

    # Instruction mentions "tích phân" but output has no integral
    if "tích phân" in instr_l and "\\int" not in output_l and "integral" not in output_l:
        issues.append("instruction nói về tích phân nhưng output không có \\int")

    # Instruction mentions "đạo hàm" but output has no derivative
    if "đạo hàm" in instr_l and "\\frac{d" not in output_l and "derivative" not in output_l:
        issues.append("instruction nói về đạo hàm nhưng output không có derivative")

    # Instruction mentions "khoảng cách" but output doesn't have abs/distance
    if "khoảng cách" in instr_l and "distance" not in output_l and "|" not in output:
        issues.append("instruction nói về khoảng cách nhưng output không có |x-y|")

    if issues:
        disconnect_count += 1
        if len(disconnect_examples) < 10:
            disconnect_examples.append((idx, entry.get("id"), instruction[:80], issues))

print(f"Entries có instruction vs output mâu thuẫn: {disconnect_count}/{len(data)}")
for ex in disconnect_examples:
    print(f"  [{ex[0]}] {ex[1]}: {ex[2]!r}")
    for iss in ex[3]:
        print(f"      - {iss}")

# ===== ISSUE 4: Reasoning generic =====
print("\n\n🚨 ISSUE 4: Reasoning quá generic")
print("=" * 80)

generic_reasoning_patterns = [
    r"đọc kỹ cấu trúc biểu thức",
    r"phân biệt biến, hằng số",
    r"không chỉ nhớ công thức một cách máy móc",
    r"biến đổi theo từng bước",
    r"Trong dạng chuẩn",
    r"thuộc về đại số",
    r"thuộc về giải tích",
]

generic_reasoning_count = 0
for idx, entry in enumerate(data):
    reasoning = entry.get("reasoning", "")
    if not reasoning:
        continue
    matches = sum(1 for pat in generic_reasoning_patterns if re.search(pat, reasoning))
    if matches >= 2:
        generic_reasoning_count += 1

print(f"Entries có reasoning quá generic: {generic_reasoning_count}/{len(data)}")

# ===== ISSUE 5: Examples không khớp =====
print("\n\n🚨 ISSUE 5: Example_problems output/solution")
print("=" * 80)

example_mismatch_count = 0
for idx, entry in enumerate(data):
    examples = entry.get("example_problems", [])
    for ex in examples:
        ex_output = ex.get("output", "")
        ex_solution = ex.get("solution", "")
        instr = entry.get("instruction", "")
        if not ex_output or not ex_solution:
            continue
        # Check if ex_solution has steps
        if not any(line.strip().startswith("Bước") for line in ex_solution.split("\n")):
            example_mismatch_count += 1

print(f"Examples thiếu steps chi tiết: {example_mismatch_count}")

# ===== ISSUE 6: Steps quá giống nhau =====
print("\n\n🚨 ISSUE 6: Steps bị trùng lặp nội dung")
print("=" * 80)

step_counter = Counter()
for idx, entry in enumerate(data):
    steps = entry.get("steps", [])
    for s in steps:
        # Normalize
        s_norm = re.sub(r"\d+", "N", s)
        step_counter[s_norm] += 1

print("Top 20 steps hay lặp lại:")
for step, count in step_counter.most_common(20):
    print(f"  ({count}x) {step[:100]}")

# ===== ISSUE 7: Steps with no real content =====
print("\n\n🚨 ISSUE 7: Steps có template cứng không theo bài toán cụ thể")
print("=" * 80)

template_steps = {
    "Bước 1: Xác định đúng bản chất của bài toán và nhận diện công thức nền tảng cần áp dụng.": 0,
    "Bước 2: Phân tích các dữ kiện đã cho để biết đâu là biến, đâu là hằng số và đâu là điều kiện xác định.": 0,
    "Bước 3: Biến đổi biểu thức theo đường lối toán học phù hợp và giữ nguyên ý nghĩa của bài toán.": 0,
    "Bước 4: Rút gọn kết quả và trình bày đáp án ở dạng chuẩn, dễ đọc và dễ kiểm tra.": 0,
}

for idx, entry in enumerate(data):
    steps = entry.get("steps", [])
    for s in steps:
        if s in template_steps:
            template_steps[s] += 1

print("Các template steps cứng:")
for s, c in sorted(template_steps.items(), key=lambda x: -x[1]):
    print(f"  ({c}x) {s}")

# ===== ISSUE 8: Reasoning sai topic =====
print("\n\n🚨 ISSUE 8: Reasoning topic không khớp instruction")
print("=" * 80)

topic_reasoning_mapping = {
    "tích phân": "giải tích",
    "đạo hàm": "giải tích",
    "logarit": "logarit",
    "phương trình": "đại số",
    "hàm số": "giải tích",
    "đồ thị": "giải tích",
    "chu vi": "hình học",
    "diện tích": "hình học",
    "thể tích": "hình học",
    "xác suất": "xác suất thống kê",
    "ma trận": "đại số",
    "vectơ": "hình học",
    "số phức": "đại số",
}

reasoning_mismatch_count = 0
for idx, entry in enumerate(data):
    instruction = entry.get("instruction", "").lower()
    reasoning = entry.get("reasoning", "").lower()
    if not reasoning:
        continue

    # Determine expected topic from instruction
    expected_topic = None
    for kw, topic in topic_reasoning_mapping.items():
        if kw in instruction:
            expected_topic = topic
            break

    # Check if reasoning mentions correct topic
    if expected_topic:
        # Check if reasoning says wrong topic
        if "thuộc về đại số" in reasoning and expected_topic in ["giải tích", "hình học", "xác suất thống kê"]:
            if "đại số" not in expected_topic:
                reasoning_mismatch_count += 1

        if "thuộc về giải tích" in reasoning and expected_topic in ["đại số", "hình học"]:
            reasoning_mismatch_count += 1

        if "thuộc về hình học" in reasoning and expected_topic in ["đại số", "giải tích"]:
            reasoning_mismatch_count += 1

print(f"Entries có reasoning sai topic: {reasoning_mismatch_count}/{len(data)}")

# ===== SUMMARY =====
print("\n" + "=" * 80)
print("📊 SUMMARY")
print("=" * 80)
print(f"  Total entries: {len(data)}")
print(f"  Generic steps: {generic_count} ({100*generic_count/len(data):.1f}%)")
print(f"  Instruction vs steps mismatch: {mismatch_count} ({100*mismatch_count/len(data):.1f}%)")
print(f"  Instruction vs output disconnect: {disconnect_count} ({100*disconnect_count/len(data):.1f}%)")
print(f"  Generic reasoning: {generic_reasoning_count} ({100*generic_reasoning_count/len(data):.1f}%)")
print(f"  Reasoning topic mismatch: {reasoning_mismatch_count} ({100*reasoning_mismatch_count/len(data):.1f}%)")