# -*- coding: utf-8 -*-
import json, random, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r"D:\Hoc_tap\The-math-latex--craw-and-ML\DATA\augmented_train_data.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print("="*80)

# Check several samples
random.seed(42)
indices = [0, 50, 200, 500, 1000]

for idx in indices:
    d = json.loads(lines[idx])
    print(f"\n{'='*80}")
    print(f"LINE {idx} | type={d.get('type')} | diff={d.get('difficulty')}")
    print("="*80)
    for m in d["messages"]:
        role = m["role"]
        content = m["content"]
        print(f"\n[{role}]:")
        print(content[:1000])
        if len(content) > 1000:
            print(f"... (truncated, total {len(content)} chars)")
    print("\n" + "-"*80)
