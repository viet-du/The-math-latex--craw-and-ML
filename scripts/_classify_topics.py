"""Phân loại bài toán tự động theo topic - kết hợp id_prefix + instruction + output LaTeX."""
import json
import re
import sys
from collections import Counter

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

with open("DATA/datasheet_final_vi3.json", "r", encoding="utf-8") as f:
    data = json.load(f)


def _classify_by_output(output):
    """Phân loại theo output LaTeX khi không rõ từ prefix/instruction."""
    if "\\int" in output:
        if "_{" in output or "^{" in output:
            return "integral"
    if "\\frac{d" in output or "\\frac{du}{d" in output or "\\frac{dy}{dx}" in output:
        return "derivative"
    if "\\sin" in output or "\\cos" in output or "\\tan" in output or "\\cot" in output:
        return "trigonometric"
    if "\\lim" in output:
        return "limit"
    if "\\log" in output or "\\ln" in output:
        return "logarithm"
    if "\\sum" in output:
        return "sequence"  # Tổng thường là dãy số
    if "\\begin{matrix}" in output or "\\begin{pmatrix}" in output or "\\begin{bmatrix}" in output:
        return "matrix"
    if "\\vec" in output or "\\overrightarrow" in output or "\\nabla" in output:
        return "vector"
    if "\\partial" in output:
        return "derivative"
    return None


def classify(entry):
    """Phân loại bài toán theo topic."""
    eid = entry.get("id", "")
    prefix = eid.split("_")[0] if "_" in eid else "unknown"

    instr = entry.get("instruction", "").lower()
    output = entry.get("output", "")
    text = instr + " " + output.lower()

    # Ưu tiên 1: Phân loại theo instruction keywords (chính xác nhất)
    # Đặc biệt áp dụng cho mọi prefix
    if "phân số" in text and ("cùng mẫu" in text or "khác mẫu" in text or "tử số" in text or "mẫu số" in text):
        return "fraction"
    if "đạo hàm" in text or "vi phân" in text or "gradient" in text:
        if "chuỗi" not in instr:
            return "derivative"
    if "tích phân" in text or "nguyên hàm" in text:
        return "integral"
    if "logarit" in text and "logarit" in instr:
        return "logarithm"
    if "lượng giác" in text or "sin" in text[:200] or "cos" in text[:200]:
        return "trigonometric"
    if "ma trận" in text or "\\begin{matrix}" in output or "\\begin{pmatrix}" in output:
        return "matrix"
    if "vectơ" in text or "vector" in text:
        return "vector"
    if "số phức" in text or "phức" in instr:
        return "complex"
    if "xác suất" in text or "probability" in text:
        return "probability"
    if "thống kê" in text or "phương sai" in text:
        return "statistics"
    if "tổ hợp" in text or "hoán vị" in text or "chỉnh hợp" in text:
        return "combinatorics"
    if "phương trình" in instr:
        return "equation"
    if "đa thức" in text:
        return "polynomial"
    if "phân tích" in instr and "nhân tử" in text:
        return "factoring"
    if "giới hạn" in text and "hàm số" in text:
        return "limit"
    if "chuỗi" in instr or "dãy số" in text or "cấp số" in text:
        return "sequence"

    # Ưu tiên 2: Theo output LaTeX (khi instruction không rõ ràng)
    out_topic = _classify_by_output(output)
    if out_topic:
        return out_topic

    # Ưu tiên 3: Theo id prefix
    if prefix == "alg":
        return "algebra_basic"
    if prefix == "linalg" or prefix == "la":
        return "linear_algebra"
    if prefix == "ml":
        return "machine_learning"
    if prefix == "dl":
        return "deep_learning"
    if prefix == "integral" or prefix == "integration" or prefix == "definite":
        return "integral"
    if prefix == "trig":
        return "trigonometric"
    if prefix == "math" or prefix == "calc":
        # Phân loại chi tiết theo output
        if "\\int" in output:
            return "integral"
        if "\\frac{d" in output or "\\partial" in output or "\\nabla" in output:
            return "derivative"
        if "\\sin" in output or "\\cos" in output or "\\tan" in output:
            return "trigonometric"
        if "\\lim" in output:
            return "limit"
        if "\\sum" in output:
            return "sequence"
        if "\\log" in output or "\\ln" in output:
            return "logarithm"
        if "\\begin{matrix}" in output or "\\begin{pmatrix}" in output:
            return "matrix"
        if "\\sqrt" in output:
            # Căn bậc hai thường là tính toán
            return "algebra_basic"
        return "math_general"

    if prefix == "ps":
        return "probability_stats"
    if prefix == "dsa":
        return "data_structure_algorithm"
    if prefix == "opt":
        return "optimization"
    if prefix == "stat":
        return "statistics"
    if prefix == "is":
        return "information_systems"
    if prefix == "geom" or prefix == "geo":
        if "thể tích" in text:
            return "geometry_solid"
        return "geometry_plane"
    if prefix == "special":
        return "special_functions"
    if prefix == "set":
        return "set_theory"
    if prefix == "prob":
        return "probability"
    if prefix == "seq":
        return "sequence"
    if prefix == "gaussian":
        return "gaussian"
    if prefix == "complex":
        return "complex"
    if prefix == "comb":
        return "combinatorics"
    if prefix == "rl":
        return "reinforcement_learning"

    return "math_general"


# Phân loại
classified = []
for e in data:
    topic = classify(e)
    e["_topic"] = topic
    classified.append(topic)

print(f"Total: {len(data)}")

counter = Counter(classified)
print("\n=== Phân loại ===")
for topic, c in counter.most_common(40):
    print(f"  {topic:30s} {c:5d}")