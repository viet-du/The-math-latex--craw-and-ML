# -*- coding: utf-8 -*-
"""Analyze what percentage of examples have REAL numbers vs text descriptions"""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"D:\Hoc_tap\The-math-latex--craw-and-ML\DATA\datasheet.json", "r", encoding="utf-8") as f:
    data = json.load(f)

real_numbers = 0
text_only = 0

for item in data:
    for ex in item.get("example_problems", []):
        vals = ex.get("input_values", {})
        # Check if ANY value is a real number (int/float) 
        has_number = any(isinstance(v, (int, float)) for v in vals.values())
        # Check for list of numbers
        has_number = has_number or any(
            isinstance(v, list) and all(isinstance(x, (int, float)) for x in v)
            for v in vals.values()
        )
        if has_number:
            real_numbers += 1
        else:
            text_only += 1

print(f"Examples with REAL numbers: {real_numbers}")
print(f"Examples with TEXT only: {text_only}")
print(f"Total: {real_numbers + text_only}")

# Show text-only keys
text_keys = set()
for item in data:
    for ex in item.get("example_problems", []):
        vals = ex.get("input_values", {})
        has_number = any(isinstance(v, (int, float)) for v in vals.values())
        has_number = has_number or any(
            isinstance(v, list) and all(isinstance(x, (int, float)) for x in v)
            for v in vals.values()
        )
        if not has_number:
            text_keys.update(vals.keys())

print(f"\nText-only example keys: {text_keys}")
