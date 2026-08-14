"""Check DSU entry after fix."""
import json
import sys
sys.stdout.reconfigure(encoding="utf-8")

with open("DATA/datasheet_final_vi3.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for e in data:
    inp = e.get("input", "")
    if "Union" in inp or "DSU" in inp:
        print("=" * 60)
        print(f"ID: {e.get('id', 'N/A')}")
        print(f"Input: {inp[:200]}")
        print(f"\nSteps:")
        for s in e.get("steps", []):
            print(f"  - {s}")
        print()
        break