"""Xem các entries equation còn generic."""
import json
import re
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

with open("DATA/datasheet_final_vi3.json.fixed", "r", encoding="utf-8") as f:
    data = json.load(f)

# Tìm entries equation còn generic
GENERIC = [
    r"^Bước \d+: Xác định đúng dạng bài toán",
    r"^Bước \d+: Đọc kỹ phương trình",
    r"^Bước \d+: Xác định đúng bản chất",
    r"^Bước \d+: Phân tích các dữ kiện",
    r"^Bước \d+: Biến đổi biểu thức",
    r"^Bước \d+: Rút gọn kết quả",
    r"^Bước \d+: Áp dụng công thức nghiệm",
    r"^Bước \d+: Kiểm tra nghiệm",
    r"^Bước \d+: Kết luận nghiệm",
]

print("=== Entries equation còn generic ===\n")
for e in data:
    if e.get("_topic") == "equation":
        for s in e.get("steps", []):
            for pat in GENERIC:
                if re.search(pat, s):
                    print(f"ID: {e.get('id', '')}")
                    print(f"Instruction: {e.get('instruction', '')}")
                    print(f"Output: {e.get('output', '')}")
                    print(f"Steps:")
                    for st in e.get("steps", []):
                        print(f"  {st}")
                    print(f"Reasoning: {e.get('reasoning', '')[:150]}...")
                    print("---")
                    break
            else:
                continue
            break