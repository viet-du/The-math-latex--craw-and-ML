"""Cleanup _topic field khỏi file chính."""
import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

with open("DATA/datasheet_final_vi3.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for e in data:
    if "_topic" in e:
        del e["_topic"]

with open("DATA/datasheet_final_vi3.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Cleaned up {len(data)} entries")

# Verify file size
import os
size = os.path.getsize("DATA/datasheet_final_vi3.json")
print(f"File size: {size:,} bytes")