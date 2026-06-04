# -*- coding: utf-8 -*-
"""Check quality of v3 augmented data"""
import json, sys, random
sys.stdout.reconfigure(encoding='utf-8')

with open(r"D:\Hoc_tap\The-math-latex--craw-and-ML\DATA\augmented_train_data.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total: {len(lines)} records\n")

# Find records WITH calculations
calc_records = []
formula_records = []
negative_records = []

for i, line in enumerate(lines):
    d = json.loads(line)
    content = d["messages"][2]["content"]
    if "Tính toán:" in content:
        calc_records.append((i, d))
    elif "SAI" in content:
        negative_records.append((i, d))
    else:
        formula_records.append((i, d))

print(f"Records with real calculations: {len(calc_records)}")
print(f"Records with formulas only: {len(formula_records)}")
print(f"Negative example records: {len(negative_records)}")

# Show 2 good calculation examples
print("\n" + "="*80)
print("EXAMPLE 1: Record with REAL CALCULATIONS")
print("="*80)
if calc_records:
    idx, d = calc_records[0]
    for m in d["messages"]:
        print(f"\n[{m['role']}]:")
        print(m["content"][:1200])

print("\n" + "="*80)
print("EXAMPLE 2: Another calculation record")
print("="*80)
if len(calc_records) > 50:
    idx, d = calc_records[50]
    for m in d["messages"]:
        print(f"\n[{m['role']}]:")
        print(m["content"][:1200])

# Show negative example
print("\n" + "="*80)
print("EXAMPLE 3: Negative example (teach model to spot errors)")
print("="*80)
if negative_records:
    idx, d = negative_records[0]
    for m in d["messages"]:
        print(f"\n[{m['role']}]:")
        print(m["content"][:800])

# Show a formula-only record
print("\n" + "="*80)
print("EXAMPLE 4: Formula-only record")
print("="*80)
if formula_records:
    idx, d = formula_records[0]
    for m in d["messages"]:
        print(f"\n[{m['role']}]:")
        print(m["content"][:800])

# Check \\boxed usage
boxed_count = sum(1 for line in lines if "\\boxed" in line)
print(f"\n\nRecords with \\boxed{{}}: {boxed_count}/{len(lines)} ({100*boxed_count/len(lines):.1f}%)")
