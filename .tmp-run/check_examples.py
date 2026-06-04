# -*- coding: utf-8 -*-
"""Check structure of example_problems in datasheet"""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"D:\Hoc_tap\The-math-latex--craw-and-ML\DATA\datasheet.json", "r", encoding="utf-8") as f:
    data = json.load(f)

has_solution = 0
no_solution = 0
total_examples = 0

# Sample some examples without solution
samples_no_sol = []
samples_with_sol = []

for item in data:
    for ex in item.get("example_problems", []):
        total_examples += 1
        if ex.get("solution"):
            has_solution += 1
            if len(samples_with_sol) < 3:
                samples_with_sol.append((item, ex))
        else:
            no_solution += 1
            if len(samples_no_sol) < 5:
                samples_no_sol.append((item, ex))

print(f"Total example_problems: {total_examples}")
print(f"  With solution field: {has_solution}")
print(f"  Without solution: {no_solution}")

print("\n" + "="*80)
print("EXAMPLES WITHOUT solution field:")
for item, ex in samples_no_sol:
    print(f"\n  Item: {item.get('id', '?')} | type: {item.get('type')}")
    print(f"  Instruction: {item.get('instruction', '')[:80]}")
    print(f"  Steps: {json.dumps(item.get('steps', [])[:2], ensure_ascii=False)[:200]}")
    print(f"  Example input_values: {ex.get('input_values', {})}")
    print(f"  Example output: {ex.get('output', '?')}")
    print(f"  Example keys: {list(ex.keys())}")
