# ════════════════════════════════════════════════════════════════
# CELL 0: EDA — DISCOVER KAGGLE CHECKPOINTS
# Paste ngay sau khi %cd vào /kaggle/working
# KHÔNG cần pip install, KHÔNG cần load model
# ════════════════════════════════════════════════════════════════

import os
import sys

# Thêm path để import hàm từ file
sys.path.insert(0, "/kaggle/working")
# Hoặc paste thẳng 2 hàm list_kaggle_checkpoints + build_adapter_dict
# vào cell này nếu không muốn import file

from inference_5agent_kaggle import (
    list_kaggle_checkpoints,
    build_adapter_dict,
)

OUTPUT_ROOT = "/kaggle/input/datasets/vitduq/train-dataa08082026/outputs"

# ── Bước 1: Scan cấu trúc thư mục ───────────────────────────
print("🚀 Bắt đầu scan checkpoints...")
sorted_ckpts = list_kaggle_checkpoints(OUTPUT_ROOT)

# ── Bước 2: Build adapter dict cho pipeline ─────────────────
print("\n📌 CHECKPOINTS ĐƯỢC CHỌN (mặc định = final hoặc cao nhất):")
print("─" * 70)
adapters = build_adapter_dict(sorted_ckpts)

# ── Bước 3: Verify từng path có file cần thiết ──────────────
print("\n🔍 VERIFY (mỗi path có adapter_config.json + weights?):")
print("─" * 70)
import os
for aid, path in adapters.items():
    if not os.path.exists(path):
        print(f"  ❌ {aid}: path không tồn tại")
        continue
    files = os.listdir(path)
    has_cfg = "adapter_config.json" in files
    has_w = any(f.endswith((".safetensors", ".bin")) for f in files)
    flag = "✅" if (has_cfg and has_w) else "⚠️"
    print(f"  {flag} {aid}: {os.path.basename(path)}/")
    print(f"      adapter_config.json: {'YES' if has_cfg else 'NO'}")
    print(f"      weights file:        {'YES' if has_w else 'NO'}")
    print(f"      total files:         {len(files)}")

# ── Bước 4: In dict cuối cùng để copy vào pipeline ──────────
print("\n" + "═" * 70)
print("📋 DICT SẴN SÀNG — copy biến `adapters` này vào các cell sau:")
print("─" * 70)
print("adapters = {")
for aid, path in adapters.items():
    print(f'    "{aid}": r"{path}",')
print("}")
print("═" * 70)