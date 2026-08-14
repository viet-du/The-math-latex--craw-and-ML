"""
Diagnostic cell - paste vào Kaggle notebook TRƯỚC khi chạy inference.
In ra cấu trúc thật của CFG.adapter_path để biết path trỏ đúng đâu.
"""

import os
from pathlib import Path

CFG_ADAPTER = "/kaggle/input/datasets/vitduq/train-modle317/outputs"

print("=" * 70)
print(f"DIAGNOSTIC: {CFG_ADAPTER}")
print("=" * 70)
print(f"Exists: {os.path.exists(CFG_ADAPTER)}")
print(f"Is dir: {os.path.isdir(CFG_ADAPTER)}")
print()

if os.path.exists(CFG_ADAPTER):
    print("[TOP-LEVEL entries]")
    for entry in sorted(os.listdir(CFG_ADAPTER)):
        full = os.path.join(CFG_ADAPTER, entry)
        kind = "DIR " if os.path.isdir(full) else "FILE"
        size = os.path.getsize(full) if os.path.isfile(full) else "-"
        print(f"  {kind}  {entry:50s}  {size}")
    print()

    # Check common checkpoint structures
    print("[CHECKPOINT SEARCH]")
    found_adapters = []
    for root, dirs, files in os.walk(CFG_ADAPTER):
        for f in files:
            if f == "adapter_config.json":
                found_adapters.append(root)

    if found_adapters:
        print(f"  Found {len(found_adapters)} adapter_config.json at:")
        for p in found_adapters:
            print(f"    {p}")
            # List sibling files
            parent = Path(p).parent
            for sibling in sorted(parent.iterdir())[:5]:
                print(f"      - {sibling.name}")
    else:
        print("  NO adapter_config.json found anywhere!")
        print("  → Bạn đang trỏ path sai. Check đúng path.")
        print()

        # Gợi ý: tìm file .safetensors hoặc .bin
        print("[SEARCHING .safetensors / .bin]")
        for root, dirs, files in os.walk(CFG_ADAPTER):
            for f in files:
                if f.endswith((".safetensors", ".bin")):
                    print(f"    {os.path.join(root, f)}")
