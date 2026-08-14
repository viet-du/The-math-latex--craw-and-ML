"""Test trực tiếp hàm EDA trên cấu trúc giả lập giống Kaggle output."""
import sys, os, tempfile, shutil

# Tạo cây thư mục giả lập
fake_root = tempfile.mkdtemp(prefix="fake_kaggle_")
print(f"Fake root: {fake_root}")

# Tạo agent1 với final + 2 checkpoint
for ckpt in ["final", "checkpoint-800", "checkpoint-447"]:
    d = os.path.join(fake_root, "agent1", ckpt)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "adapter_config.json"), "w") as f:
        f.write('{"r": 16, "lora_alpha": 32}')
    with open(os.path.join(d, "adapter_model.safetensors"), "wb") as f:
        f.write(b"\x00" * 100)

# Tạo agent2 chỉ có final
d = os.path.join(fake_root, "agent2", "final")
os.makedirs(d, exist_ok=True)
with open(os.path.join(d, "adapter_config.json"), "w") as f:
    f.write('{"r": 32}')
with open(os.path.join(d, "adapter_model.safetensors"), "wb") as f:
    f.write(b"\x00" * 100)

# Tạo agent3 với 3 checkpoint (không có adapter_config ở 2 cái sau)
for ckpt in ["final", "checkpoint-200", "checkpoint-100"]:
    d = os.path.join(fake_root, "agent3", ckpt)
    os.makedirs(d, exist_ok=True)
    if ckpt == "final":
        with open(os.path.join(d, "adapter_config.json"), "w") as f:
            f.write('{"r": 16}')
    with open(os.path.join(d, "adapter_model.safetensors"), "wb") as f:
        f.write(b"\x00" * 100)

# Tạo training_history.json giả
import json
hist = {
    "agent1": {
        "train_loss": [2.5, 2.1, 1.8, 1.5, 1.2, 1.0, 0.9, 0.8, 0.7, 0.6, 0.55],
        "eval_loss":  [2.4, 2.0, 1.7, 1.4, 1.1, 0.95, 0.85, 0.75, 0.65, 0.58, 0.52],
        "learning_rate": [1e-4, 9e-5, 8e-5, 7e-5, 6e-5, 5e-5, 4e-5, 3e-5, 2e-5, 1e-5, 5e-6],
    },
    "agent2": {
        "train_loss": [3.0, 2.5, 2.0, 1.8, 1.5, 1.3, 1.1, 0.9, 0.8, 0.7, 0.65],
        "eval_loss":  [2.9, 2.4, 1.9, 1.7, 1.4, 1.2, 1.0, 0.85, 0.75, 0.68, 0.63],
        "learning_rate": [1e-4] * 11,
    },
    "agent3": {
        "train_loss": [3.5, 3.3, 3.2, 3.1, 3.05, 3.0, 2.95, 2.9, 2.85, 2.8, 2.78],
        "eval_loss":  [3.4, 3.25, 3.15, 3.05, 3.0, 2.95, 2.9, 2.85, 2.8, 2.78, 2.75],
        "learning_rate": [1e-4] * 11,
    },
}
hist_path = os.path.join(fake_root, "training_history.json")
with open(hist_path, "w") as f:
    json.dump(hist, f, indent=2)

print(f"Fake structure ready\n")

# ── Import hàm từ FILE STANDALONE (không bị crash do emoji) ──
import importlib.util
spec = importlib.util.spec_from_file_location(
    "eda_standalone",
    r"d:\Hoc_tap\The-math-latex--craw-and-ML\train_model\eda_standalone.py"
)
eda_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eda_mod)

list_kaggle_checkpoints = eda_mod.list_kaggle_checkpoints
build_adapter_dict      = eda_mod.build_adapter_dict
eda_training_loss       = eda_mod.eda_training_loss

# ── TEST 1: list_kaggle_checkpoints ──
print("=" * 70)
print("TEST 1: list_kaggle_checkpoints()")
print("=" * 70)
sorted_ckpts = list_kaggle_checkpoints(fake_root)
print(f"\n--> Returned: {dict(sorted_ckpts)}\n")

# ── TEST 2: build_adapter_dict ──
print("=" * 70)
print("TEST 2: build_adapter_dict()")
print("=" * 70)
adapters = build_adapter_dict(sorted_ckpts)
print(f"\n--> Returned: {adapters}\n")

# ── TEST 3: eda_training_loss ──
print("=" * 70)
print("TEST 3: eda_training_loss()")
print("=" * 70)
plots_dir = os.path.join(fake_root, "plots")
os.makedirs(plots_dir, exist_ok=True)
summary = eda_training_loss(hist_path, plots_dir=plots_dir)

# ── Cleanup ──
print(f"\n\nPlots dir: {plots_dir}")
for f in os.listdir(plots_dir):
    print(f"  📊 {f}")