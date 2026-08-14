"""Lấy các mẫu input_variants có tiếng Anh."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

with open("DATA/datasheet_final_vi3.json", "r", encoding="utf-8") as f:
    d = json.load(f)

# Lấy các mẫu input_variants có tiếng Anh
for e in d[:20]:
    iv = e.get("input_variants", [])
    for v in iv:
        if any(w in v for w in ["Sử dụng", "use ", "apply", "growing", "with", "for ", "find", "Find"]):
            iid = e.get("id", "")
            print(f"ID: {iid}")
            print(f"  {v}")
            print()