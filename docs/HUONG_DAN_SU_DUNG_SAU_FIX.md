# HƯỚNG DẪN SỬ DỤNG SAU KHI FIX

## Các Thay Đổi Đã Thực Hiện

### 1. Training Script (`qwen25_math_5agent_lora_kaggle.py`)
- ✅ Đã fix `add_generation_prompt=False` trong tokenization (line ~400)
- ⚠️ Cần re-train vì model cũ được train với config sai

### 2. Inference Script (`inference_vietnamese.py`) - FILE MỚI
- ✅ Prompts hoàn toàn tiếng Việt (khớp với training)
- ✅ Generation config đúng (greedy decoding)
- ✅ Sử dụng `agent_max_tokens = 512`
- ✅ Chat template đúng cách

### 3. Data Transform Script (`transform_data.py`) - FILE MỚI
- ✅ Chuyển đổi datasheet.json → training format
- ✅ Prompts tiếng Việt cho 5 agents
- ✅ Split train/val tự động

---

## THỨ TỰ THỰC HIỆN

### Bước 1: Transform Data (Tạo training data mới)
```bash
cd D:\Hoc_tap\The-math-latex--craw-and-ML

python scripts/transform_data.py \
    --input DATA/datasheet.json \
    --output DATA/transformed
```

### Bước 2: Train Model (Re-train với config đúng)
```bash
# Trên Kaggle, chạy:
python qwen25_math_5agent_lora_kaggle.py
```

**Thay đổi cấu hình trong script nếu cần:**
```python
class CFG:
    data_dir = "./DATA/transformed"  # Thư mục data đã transform
    epochs = 3-5  # Tăng nếu model còn yếu
    max_seq_len = 512  # Đủ cho lời giải dài
```

### Bước 3: Upload Adapters Lên Kaggle
```bash
# Sau khi train xong, upload thư mục outputs/ lên Kaggle
# Cập nhật adapter_path trong inference script
```

### Bước 4: Chạy Inference
```bash
# Test với một bài toán
python train_model/inference_vietnamese.py \
    --problem "Một người có 50 quả táo. Bán đi 3/5 số táo. Hỏi còn lại bao nhiêu quả?"

# Hoặc chế độ tương tác
python train_model/inference_vietnamese.py --interactive
```

---

## CẤU TRÚC FILE SAU KHI HOÀN THÀNH

```
D:\Hoc_tap\The-math-latex--craw-and-ML\
├── DATA/
│   ├── datasheet.json                    # Raw data
│   └── transformed/                      # Training data (sau khi transform)
│       ├── agent1_train.jsonl
│       ├── agent1_val.jsonl
│       ├── agent2_train.jsonl
│       ├── agent2_val.jsonl
│       ├── agent3_train.jsonl
│       ├── agent3_val.jsonl
│       ├── agent4_train.jsonl
│       ├── agent4_val.jsonl
│       ├── agent5_train.jsonl
│       └── agent5_val.jsonl
│
├── train_model/
│   ├── qwen25_math_5agent_lora_kaggle.py # Training script (đã fix)
│   ├── inference_vietnamese.py           # Inference script (mới)
│   └── outputs/                          # Trained adapters
│       ├── agent1/
│       ├── agent2/
│       ├── agent3/
│       ├── agent4/
│       └── agent5/
│
├── scripts/
│   └── transform_data.py                 # Script transform data (mới)
│
└── pipeline_plan_vietnamese_math.md     # Kế hoạch chi tiết
```

---

## KIỂM TRA KẾT QUẢ

### Dấu hiệu Model Hoạt Động Đúng:
1. ✅ Output hoàn toàn **tiếng Việt**
2. ✅ Có `\boxed{đáp án}` ở cuối
3. ✅ Các bước giải logic, rõ ràng
4. ✅ Không lặp, không vô nghĩa

### Dấu hiệu Model Còn Lỗi:
1. ❌ Output tiếng Anh/Trung
2. ❌ Không có `\boxed{}`
3. ❌ Lặp câu, vô nghĩa
4. ❌ Đáp án sai

---

## CÁC LỖI ĐÃ FIX

| Lỗi | File | Fix |
|------|------|-----|
| Prompts không khớp | `inference_vietnamese.py` | Dùng prompts tiếng Việt |
| `add_generation_prompt=True` training | `qwen25_math_5agent_lora_kaggle.py` | Đổi thành `False` |
| `temperature=0.5` + `do_sample=False` | `inference_vietnamese.py` | Bỏ temperature, giữ greedy |
| `max_tokens=384` quá ngắn | `inference_vietnamese.py` | Tăng lên 512 |

---

## HYPERPARAMETERS KHUYẾN NGHỊ

```python
# Training
lr = 2e-4
epochs = 3-5
batch_size = 2-4
lora_r = 64  # Cho agent3 (reasoning)
lora_r = 32  # Cho agent2 (classification)
lora_r = 16  # Cho agent1, 4, 5

# Inference
max_new_tokens = 512
do_sample = False  # Greedy cho toán
temperature = None  # Không cần
```

---

## NẾU VẪN CÓ VẤN ĐỀ

### Vấn đề: Model vẫn output tiếng Anh
→ Kiểm tra lại training data có đúng tiếng Việt không
→ Re-train với data đã clean

### Vấn đề: Model lặp
→ Giảm `max_new_tokens` xuống 384
→ Tăng `temperature` lên 0.3 (nếu cần sampling)

### Vấn đề: OOM khi train
→ Giảm `batch_size` xuống 1
→ Bật gradient checkpointing
→ Giảm `max_seq_len` xuống 384

---

**Ngày cập nhật**: 2026-08-05
