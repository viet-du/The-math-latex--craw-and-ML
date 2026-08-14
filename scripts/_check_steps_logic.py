"""Inspect specific entries with issues."""
import json
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

with open('DATA/datasheet_final_vi3.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Check entry 201 (gaussian_integral_4)
for idx in [201, 224, 230, 259, 418]:
    e = data[idx]
    print(f"\n=== Entry {idx} id={e.get('id')} ===")
    print(f"instruction: {e.get('instruction')!r}")
    print(f"output: {e.get('output')!r}")
    print(f"steps:")
    for s in e.get('steps', []):
        print(f"  - {s}")
    print(f"reasoning: {e.get('reasoning', '')[:200]!r}")