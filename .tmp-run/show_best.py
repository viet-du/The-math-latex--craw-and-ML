# -*- coding: utf-8 -*-
"""Show best quality records from v3.1"""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"D:\Hoc_tap\The-math-latex--craw-and-ML\DATA\augmented_train_data.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find calc_ibp or alg_quadratic examples (boost data)
count = 0
for i, line in enumerate(lines):
    d = json.loads(line)
    content = d["messages"][2]["content"]
    user = d["messages"][1]["content"]
    
    # Tìm bài có tính toán thật sự tốt
    if ("tích phân" in user.lower() and "Tính toán" in content and 
        d["type"] == "calculus"):
        print(f"{'='*80}")
        print(f"RECORD {i} | type={d['type']} | diff={d['difficulty']}")
        print(f"{'='*80}")
        for m in d["messages"]:
            print(f"\n[{m['role']}]:")
            print(m["content"])
        print()
        count += 1
        if count >= 2:
            break

# Also find an algebra example with numbers
count2 = 0
for i, line in enumerate(lines):
    d = json.loads(line)
    content = d["messages"][2]["content"]
    user = d["messages"][1]["content"]
    
    if d["type"] == "algebra" and "Cho biết" in user and "numerator" in user.lower():
        print(f"{'='*80}")
        print(f"RECORD {i} | type={d['type']} | diff={d['difficulty']}")
        print(f"{'='*80}")
        for m in d["messages"]:
            print(f"\n[{m['role']}]:")
            print(m["content"])
        print()
        count2 += 1
        if count2 >= 1:
            break
