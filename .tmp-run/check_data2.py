# -*- coding: utf-8 -*-
"""Inspect datasheet.json structure - check if example_problems have real numbers"""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"D:\Hoc_tap\The-math-latex--craw-and-ML\DATA\datasheet.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Count items with/without example_problems with actual numbers
has_examples = 0
no_examples = 0
has_good_steps = 0  # steps that contain actual numbers/calculations

for item in data[:50]:  # Check first 50
    exps = item.get("example_problems", [])
    if exps and len(exps) > 0:
        has_examples += 1
    else:
        no_examples += 1
    
    steps = item.get("steps", [])
    step_text = " ".join(str(s) for s in steps) if isinstance(steps, list) else str(steps)
    # Check if steps contain actual numbers
    import re
    if re.search(r'\d+\s*[+\-*/=]', step_text) or re.search(r'=\s*\d+', step_text):
        has_good_steps += 1

print(f"First 50 items:")
print(f"  Has example_problems: {has_examples}")
print(f"  No example_problems: {no_examples}")
print(f"  Steps with actual calculations: {has_good_steps}")

# Show a boost data item to see quality
boost_ids = ["calc_ibp_xe_x", "calc_definite_ibp_xe_x", "alg_quadratic_formula_full", "seq_arithmetic_sum"]
print("\n" + "="*80)
print("BOOST DATA ITEMS (from add_boost_data.py):")
for item in data:
    if item.get("id") in boost_ids:
        print(f"\n--- {item['id']} ---")
        print(f"Steps: {json.dumps(item.get('steps', []), ensure_ascii=False, indent=2)[:500]}")
        exps = item.get("example_problems", [])
        if exps:
            print(f"Examples: {json.dumps(exps[:2], ensure_ascii=False, indent=2)[:400]}")
        print()

# Show a REGULAR data item for comparison
print("="*80)
print("REGULAR DATA ITEMS (non-boost):")
for item in data[:20]:
    if item.get("id") not in boost_ids and item.get("type") in ("algebra", "calculus"):
        print(f"\n--- {item['id']} (type={item.get('type')}) ---")
        print(f"Instruction: {item.get('instruction', '')[:100]}")
        print(f"Steps: {json.dumps(item.get('steps', []), ensure_ascii=False, indent=2)[:500]}")
        exps = item.get("example_problems", [])
        if exps:
            print(f"Examples: {json.dumps(exps[:1], ensure_ascii=False, indent=2)[:300]}")
        else:
            print("Examples: NONE")
        print()
        break
