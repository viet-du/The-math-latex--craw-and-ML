"""Phân tích các dạng bài trong dataset + phân loại topic."""
import json
import re
import sys
from collections import Counter, defaultdict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

with open("DATA/datasheet_final_vi3.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total: {len(data)}")

# Phân loại theo id prefix
prefix_counter = Counter()
for e in data:
    eid = e.get("id", "")
    prefix = eid.split("_")[0] if "_" in eid else "unknown"
    prefix_counter[prefix] += 1

print("\n=== Theo id prefix ===")
for p, c in prefix_counter.most_common(30):
    print(f"  {p:30s} {c:5d}")

# Phân loại theo instruction topic
print("\n=== Phân loại theo instruction topic ===")
topic_keywords = {
    "fraction": ["phân số", "fraction", "tử số", "mẫu số"],
    "equation": ["phương trình", "equation", "nghiệm"],
    "system_eq": ["hệ phương trình"],
    "inequality": ["bất phương trình", "inequality"],
    "derivative": ["đạo hàm", "vi phân", "derivative"],
    "integral": ["tích phân", "nguyên hàm", "integral"],
    "limit": ["giới hạn", "limit"],
    "logarithm": ["logarit", "logarithm", "ln"],
    "exponential": ["số mũ", "lũy thừa", "mũ", "exponential"],
    "trigonometric": ["sin", "cos", "tan", "cot", "lượng giác", "trigonometric"],
    "polynomial": ["đa thức", "polynomial"],
    "matrix": ["ma trận", "matrix", "định thức", "determinant"],
    "vector": ["vectơ", "vector"],
    "complex": ["số phức", "complex"],
    "geometry_plane": ["tam giác", "hình vuông", "hình chữ nhật", "đường tròn", "chu vi", "diện tích"],
    "geometry_solid": ["thể tích", "hình cầu", "hình trụ", "hình nón"],
    "probability": ["xác suất", "probability"],
    "statistics": ["thống kê", "mean", "variance", "trung bình", "phương sai"],
    "series": ["chuỗi", "series", "tổng", "tích phân"],
    "combinatorics": ["tổ hợp", "hoán vị", "chỉnh hợp", "combination"],
    "graph": ["đồ thị", "graph", "vẽ"],
    "algebra_basic": ["cộng", "trừ", "nhân", "chia", "đẳng thức", "biểu thức"],
    "function": ["hàm số", "function"],
    "factoring": ["phân tích thành nhân tử", "factor"],
    "inequality_short": ["bất đẳng thức", "AM-GM", "Cauchy"],
    "number_theory": ["số nguyên tố", "ước chung", "bội chung", "số học"],
    "sequence": ["dãy số", "cấp số"],
}

topic_counter = Counter()
multi_topic = 0
for e in data:
    instr = e.get("instruction", "").lower()
    output = e.get("output", "").lower()
    text = instr + " " + output
    topics = []
    for topic, kws in topic_keywords.items():
        for kw in kws:
            if kw in text:
                topics.append(topic)
                break
    if topics:
        topic_counter[topics[0]] += 1
    else:
        topic_counter["unknown"] += 1
    if len(topics) > 1:
        multi_topic += 1

print("\nSố entries có > 1 topic:", multi_topic)
for t, c in topic_counter.most_common(40):
    print(f"  {t:30s} {c:5d}")

# Phân loại theo output pattern
print("\n=== Phân loại theo output LaTeX ===")

output_patterns = {
    "integral": r"\\int",
    "derivative": r"\\frac\{d[xy]?\}",
    "sqrt": r"\\sqrt",
    "sum": r"\\sum",
    "matrix": r"\\begin\{p?matrix\}",
    "binom": r"\\binom",
    "frac": r"\\frac",
    "limit": r"\\lim",
    "trig_func": r"\\sin|\\cos|\\tan|\\cot",
}

pattern_counter = Counter()
for e in data:
    output = e.get("output", "")
    patterns = []
    for p, pat in output_patterns.items():
        if re.search(pat, output):
            patterns.append(p)
    if patterns:
        key = ",".join(sorted(patterns))
        pattern_counter[key] += 1

print("\nTop 20 output patterns:")
for p, c in pattern_counter.most_common(20):
    print(f"  ({c:4d}) {p}")