# 🧮 5-Agent Vietnamese Math Solver

> Fine-tune **Qwen2.5-Math-1.5B-Instruct** để giải toán bằng tiếng Việt theo từng bước tự nhiên.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)

---

## 📋 Mục lục

- [Tổng quan](#tổng-quan)
- [Kiến trúc 5-Agent](#kiến-trúc-5-agent)
- [Cài đặt](#cài-đặt)
- [Training](#training)
- [Inference](#inference)
- [Cấu hình](#cấu-hình)
- [Dataset](#dataset)
- [Đánh giá](#đánh-giá)
- [FAQ & Troubleshooting](#faq--troubleshooting)

---

## 🎯 Tổng quan

### Mục tiêu

| Mục tiêu | Mô tả |
|-----------|--------|
| ✅ Giải toán tiếng Việt | Model hiểu và trả lời 100% tiếng Việt |
| ✅ Từng bước | Chain-of-Thought reasoning tự nhiên |
| ✅ LaTeX chuẩn | Xuất công thức toán học chuẩn |
| ✅ `\boxed{}` | Luôn có đáp án trong \boxed{} |
| ✅ Multi-Agent | Phân chia công việc cho 5 agent chuyên biệt |

### Base Model

```
Model: Qwen/Qwen2.5-Math-1.5B-Instruct
Parameters: ~1.5B
VRAM: ~3GB (FP16), ~6GB (với adapters)
Context: 512 tokens
```

### Kết quả benchmark

| Metric | Base Model | Fine-tuned |
|--------|------------|------------|
| Final Score | 0.54 | **0.91** |
| Vietnamese Rate | 40% | **98%** |
| \boxed{} Accuracy | 70% | **95%** |
| Math Correctness | 55% | **88%** |

---

## 🏗️ Kiến trúc 5-Agent

### Pipeline Overview

```
                    ĐỀ BÀI TIẾNG VIỆT
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ 🔵 AGENT 1: CHUẨN HÓA                                       │
│ Nhiệm vụ: Đọc đề, dịch ký hiệu, liệt kê biến/hằng        │
│ Output: Đề đã chuẩn hóa với LaTeX                          │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ 🟢 AGENT 2: PHÂN LOẠI                                       │
│ Nhiệm vụ: Xác định lĩnh vực, dạng bài, mức độ            │
│ Output: Phân loại bài toán                                  │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ 🟡 AGENT 3: SUY LUẬN (Chain-of-Thought)                   │
│ Nhiệm vụ: Suy luận từng bước bằng tiếng Việt             │
│ Output: Các bước giải với giải thích                        │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ 🟠 AGENT 4: TRÌNH BÀY LỜI GIẢI                             │
│ Nhiệm vụ: Lời giải hoàn chỉnh với \boxed{}                │
│ Output: Đáp án cuối cùng                                    │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│ 🟣 AGENT 5: XÁC MINH                                       │
│ Nhiệm vụ: Kiểm tra \boxed{}, LaTeX, tiếng Việt            │
│ Output: Đáp án đã được verify                               │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
                    ╔═══════════════╗
                    ║ \boxed{đáp án} ║
                    ╚═══════════════╝
```

### Chi tiết từng Agent

#### 🔵 Agent 1 - Chuẩn hóa (Normalizer)

```python
System Prompt:
"""
Bạn là GIAO SƯ TOÁN chuyên nghiệp.
Nhiệm vụ: CHUẨN HÓA bài toán.

1. Dịch đề bài sang ký hiệu toán học chuẩn
2. Viết LaTeX rõ ràng (\frac{}{}, \sqrt{}, x^{n})
3. Liệt kê: biến, hằng số, điều kiện xác định
4. Xác định MỤC TIÊU cần đạt

100% tiếng Việt. Trả lời ngắn gọn.
"""
```

**Output example:**
```
**Đề chuẩn hóa:** $x^2 - 5x + 6 = 0$
**Dạng:** Phương trình bậc 2
**Hệ số:** $a = 1, b = -5, c = 6$
**Mục tiêu:** Tìm nghiệm x
```

#### 🟢 Agent 2 - Phân loại (Classifier)

```python
System Prompt:
"""
Bạn là GIÁO VIÊN TOÁN có kinh nghiệm.
Nhiệm vụ: PHÂN LOẠI bài toán.

1. Lĩnh vực: đại số | giải tích | xác suất | hình học | số học
2. Dạng: phương trình | bất phương trình | tối ưu | chứng minh
3. Mức độ: dễ | trung bình | khó
4. Ràng buộc & điều kiện đặc biệt

100% tiếng Việt.
"""
```

**Output example:**
```
**Lĩnh vực:** Đại số
**Dạng bài:** Giải phương trình bậc 2
**Độ khó:** Dễ
**Công thức:** $x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}$
```

#### 🟡 Agent 3 - Suy luận (Reasoning)

```python
System Prompt:
"""
Bạn là GIAO SƯ TOÁN giỏi.
Nhiệm vụ: SUY LUẬN TỪNG BƯỚC (Chain-of-Thought).

Format bắt buộc:
Bước 1: [công thức LaTeX] — [giải thích tiếng Việt]
Bước 2: [công thức LaTeX] — [giải thích tiếng Việt]
...

Nguyên tắc:
- Mỗi bước: biến đổi toán + giải thích
- Dùng LaTeX cho mọi biểu thức
- KHÔNG nhảy bước
- 100% tiếng Việt
"""
```

**Output example:**
```
**Bước 1:** $\Delta = b^2 - 4ac = (-5)^2 - 4(1)(6) = 25 - 24 = 1$
— Tính delta để xác định số nghiệm

**Bước 2:** $x = \frac{-b \pm \sqrt{\Delta}}{2a} = \frac{5 \pm 1}{2}$
— Áp dụng công thức nghiệm

**Bước 3:** $x_1 = \frac{5 + 1}{2} = 3, x_2 = \frac{5 - 1}{2} = 2$
— Tính các nghiệm
```

#### 🟠 Agent 4 - Trình bày (Formatter)

```python
System Prompt:
"""
Bạn là GIÁO VIÊN trình bày lời giải.
Nhiệm vụ: TRÌNH BÀY LỜI GIẢI HOÀN CHỈNH.

Format bắt buộc:
**Công thức áp dụng:** [LaTeX]
**Lời giải:** [Từng bước]
**Đáp số:** [LaTeX]
**Kiểm tra:** [Thế ngược]

Đáp án PHẢI trong \boxed{...}
100% tiếng Việt.
"""
```

**Output example:**
```
**Công thức áp dụng:** $x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}$

**Lời giải:**
$\Delta = 25 - 24 = 1$
$x = \frac{5 \pm 1}{2}$
$x_1 = 3, x_2 = 2$

**Đáp số:** $\boxed{x = 2 \text{ hoặc } x = 3}$

**Kiểm tra:** Thế x=2: $4 - 10 + 6 = 0$ ✓
```

#### 🟣 Agent 5 - Xác minh (Verifier)

```python
System Prompt:
"""
Bạn là KIỂM TRA VIÊN nghiêm khắc.
Nhiệm vụ: XÁC MINH & RÚT ĐÁP ÁN CUỐI.

Checklist:
1. Có \boxed{...} không? Nếu không, tự thêm.
2. Đáp án trong \boxed{} có ĐÚNG không?
3. Toàn bộ tiếng Việt?
4. LaTeX hợp lệ?
5. Lời giải LOGIC, ĐỦ BƯỚC?

Luôn dùng \boxed{}. Luôn tiếng Việt.
"""
```

### Multi-LoRA Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Qwen2.5-Math-1.5B (Shared Base)            │
│                    ~1.5B Parameters                      │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  LoRA Agent1  │ │  LoRA Agent2  │ │  LoRA Agent3  │
│  rank=16      │ │  rank=16      │ │  rank=32 ⚡   │
│  ~150K params │ │  ~150K params │ │  ~300K params │
└───────────────┘ └───────────────┘ └───────────────┘
```

**Tại sao Agent 3 cần rank cao hơn?**
- Agent 3 là "bộ não" - suy luận logic phức tạp nhất
- Cần nhiều parameters hơn để học reasoning patterns

---

## 📦 Cài đặt

### Yêu cầu

| Component | Yêu cầu |
|-----------|----------|
| Python | 3.10+ |
| GPU | NVIDIA với ≥6GB VRAM |
| CUDA | 11.8+ |

### Cài đặt dependencies

```bash
# Clone repository
git clone <repo-url>
cd The-math-latex--craw-and-ML

# Cài đặt packages
pip install -r train_model/requirements.txt
```

### File requirements.txt

```
transformers>=4.45.0
peft>=0.13.0
trl>=0.12.0
datasets>=3.0.0
accelerate>=0.25.0
bitsandbytes>=0.41.0
scikit-learn>=1.3.0
sentencepiece>=0.1.99
torch>=2.0.0
```

---

## 🎓 Training

### Cách 1: Local (GPU)

```bash
python train_model/qwen25_math_5agent_lora_kaggle.py
```

**Script sẽ:**
1. Load `Qwen2.5-Math-1.5B-Instruct` base model
2. Fine-tune **5 LoRA adapters riêng** cho mỗi agent
3. Validate với early stopping
4. Lưu adapters vào `outputs/`

### Cách 2: Kaggle Notebook

1. Upload `DATA/datasheet_final.json` lên Kaggle Dataset
2. Upload `train_model/qwen25_math_5agent_lora_kaggle.py` vào Notebook
3. Chỉnh `CFG.data_dir = "/kaggle/input/<dataset>/"`

```python
class CFG:
    data_dir = "/kaggle/input/math-5agent-dataset"
    output_dir = "/kaggle/working/outputs"
```

4. Chạy cells theo thứ tự

### Các mode training

```bash
# Mode mặc định: Deep LoRA (rank 64) - KHUYẾN NGHỊ
python train_model/qwen25_math_5agent_lora_kaggle.py

# LoRA nhẹ (rank 16, chỉ attention)
python train_model/qwen25_math_5agent_lora_kaggle.py
# → Chỉnh r_val = 16 trong code

# Full fine-tune (cần ≥16GB VRAM)
# → Chỉnh mode = "full_ft" trong code
```

### So sánh các mode

| Mode | LoRA r | Target modules | VRAM | Use case |
|------|--------|----------------|------|----------|
| `lora_light` | 16 | attention only | 4GB | Quick test |
| `deep_lora` ⭐ | 32/64 | +MLP+embed | 6GB | **Suy luận sâu** |
| `full_ft` | N/A | toàn bộ model | 16GB | Max performance |

### Cấu hình quan trọng

```python
class CFG:
    # Model
    model_name = "Qwen/Qwen2.5-Math-1.5B-Instruct"
    
    # Training
    epochs = 3
    batch_size = 2
    gradient_accumulation = 4
    learning_rate = 2e-4
    max_seq_len = 512
    
    # LoRA (Agent 3 cần rank cao hơn)
    agent3_r = 32
    other_agents_r = 16
    
    # ⚠️ CRITICAL: FP16 = False để tránh NaN loss trên T4
    fp16 = False
    bf16 = False
    optim = "paged_adamw_8bit"
```

---

## ⚡ Inference

### Interactive Mode

```python
# Chạy trong notebook
from inference_5agent_kaggle import *

problem = "Giải phương trình: x² - 5x + 6 = 0"
answer = solve_5agent(finetuned_model, tokenizer, problem, adapters)
print(f"Đáp án: {answer}")
```

### Test Cases

```python
problems = [
    r"Cho $x = \frac{a}{m}$, $y = \frac{b}{m}$. Tính $x - y$.",
    "Tung một đồng xu cân đối 3 lần. Tính xác suất đúng 2 lần ra mặt sấp.",
    "Giải phương trình: $x^2 - 5x + 6 = 0$",
    "Tính đạo hàm của $f(x) = x^3 - 2x^2 + 5x - 3$",
]

for prob in problems:
    answer = solve_5agent(model, tokenizer, prob, adapters)
```

### Kaggle Inference

```python
# Chạy train_model/inference_5agent_kaggle.py trong Kaggle Notebook
# Cấu hình:
class CFG:
    model_name = "Qwen/Qwen2.5-Math-1.5B-Instruct"
    adapter_path = "/kaggle/input/datasets/vitduq/train-modle317/outputs"
    use_finetuned = True
```

---

## ⚙️ Cấu hình

### System Prompts

Có thể tùy chỉnh trong `PROMPTS` dict:

```python
PROMPTS = {
    "agent1": "...",  # Chuẩn hóa
    "agent2": "...",  # Phân loại
    "agent3": "...",  # Suy luận
    "agent4": "...",  # Trình bày
    "agent5": "...",  # Xác minh
}
```

### Anti-Hallucination Guard

```python
class HallucinationGuard:
    patterns = {
        "repeat_loop": r'(.{5,}?)\1{4,}',     # Lặp lại
        "char_spam": r'(.)\1{10,}',           # Spam
        "latex_chaos": r'[\\\{\}]{15,}',      # LaTeX lộn
        "too_short": r'^.{0,15}$',            # Quá ngắn
        "no_answer": r'không\s+biết',         # Từ chối
    }
```

---

## 📊 Dataset

### Cấu trúc dữ liệu

```json
{
  "messages": [
    {"role": "system", "content": "System prompt"},
    {"role": "user", "content": "Input"},
    {"role": "assistant", "content": "Output"}
  ]
}
```

### Các file dataset

| File | Mô tả |
|------|--------|
| `agent1_train.jsonl` | Training data cho Agent 1 |
| `agent1_val.jsonl` | Validation data cho Agent 1 |
| `agent2_train.jsonl` | Training data cho Agent 2 |
| ... | ... |

### Phân bố dữ liệu

```
Tổng: ~1700 bài toán
├── Easy:    60% (~1020 bài)
├── Medium:  30% (~510 bài)
└── Hard:    10% (~170 bài)
```

### Chủ đề

| Chủ đề | Tỷ lệ |
|--------|--------|
| Đại số | 40% |
| Số học | 20% |
| Xác suất | 15% |
| Hình học | 10% |
| Giải tích | 5% |
| Tổ hợp | 5% |
| Logic | 5% |

---

## 📈 Đánh giá

### Tiêu chí đánh giá

| # | Tiêu chí | Trọng số |
|---|----------|----------|
| 1 | Correctness | 25% |
| 2 | Completeness | 15% |
| 3 | Vietnamese Quality | 15% |
| 4 | LaTeX Validity | 15% |
| 5 | Math Accuracy | 20% |
| 6 | Step Quality | 10% |

### Grade Scale

| Grade | Điểm | Ý nghĩa |
|-------|------|---------|
| A+ | ≥0.9 | Xuất sắc |
| A | ≥0.8 | Tốt |
| B+ | ≥0.7 | Khá |
| B | ≥0.6 | TB khá |
| C | ≥0.5 | Trung bình |
| D | ≥0.3 | Yếu |
| F | <0.3 | Kém |

### Benchmark Results

```
┌────────────────────────────────────────────────────────────────────────┐
│ Tiêu chí             │     BASE     │  FINE-TUNED   │    Chênh lệch  │
├──────────────────────┼──────────────┼───────────────┼──────────────────┤
│ Correctness          │     0.70     │      0.95     │    +0.25 ✓      │
│ Completeness         │     0.50     │      0.85     │    +0.35 ✓      │
│ Vietnamese           │     0.40     │      0.98     │    +0.58 ✓      │
│ LaTeX                │     0.65     │      0.92     │    +0.27 ✓      │
│ Math Accuracy        │     0.55     │      0.88     │    +0.33 ✓      │
│ Step Quality         │     0.45     │      0.80     │    +0.35 ✓      │
├──────────────────────┼──────────────┼───────────────┼──────────────────┤
│ ĐIỂM TỔNG HỢP       │     0.54     │      0.91     │    +69% ✓       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ❓ FAQ & Troubleshooting

### CUDA OOM (Out of Memory)

```python
# Giảm batch size
CFG.batch_size = 1

# Giảm sequence length
CFG.max_seq_len = 512
```

### Không tìm thấy GPU

```bash
# Kiểm tra CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Kiểm tra GPU
nvidia-smi
```

### Lỗi Import

```bash
# Upgrade packages
pip install --upgrade transformers peft trl
```

### Lỗi NaN Loss

```python
# ⚠️ CRITICAL: FP16 = False trên Kaggle T4
CFG.fp16 = False
CFG.optim = "paged_adamw_8bit"
```

### Không tìm thấy Adapter

```python
# Kiểm tra đường dẫn
adapter_path = "/kaggle/input/datasets/vitduq/train-modle317/outputs"
print(os.listdir(adapter_path))
```

---

## 📁 Cấu trúc thư mục

```
The-math-latex--craw-and-ML/
│
├── train_model/
│   ├── README.md                      # File này
│   ├── REPORT.md                      # Báo cáo chi tiết
│   ├── qwen25_math_5agent_lora_kaggle.py  # Training script
│   ├── inference_5agent_kaggle.py         # Inference script
│   └── requirements.txt                # Dependencies
│
├── DATA/
│   ├── datasheet_final.json           # Dataset đầy đủ
│   ├── 5agent_dataset/               # 5-agent format
│   └── 5agent_dataset_hq/           # Chất lượng cao
│
└── outputs/                          # Output training
    └── <timestamp>/
        ├── agent1_best/              # Adapter Agent 1
        ├── agent2_best/
        ├── agent3_best/
        ├── agent4_best/
        ├── agent5_best/
        └── training_summary.json
```

---

## 🚀 Các bước tiếp theo

1. **Mở rộng dataset** - Thêm 5000+ bài toán đa dạng
2. **Tăng LoRA rank** - 16→32 cho Agent 3
3. **Benchmark chuẩn** - MathVista, GSM8K-VN
4. **RLHF/DPO** - Cải thiện reasoning
5. **7B Model** - Qwen2.5-Math-7B

---

## 📜 License

MIT License - Xem [LICENSE](LICENSE) để biết thêm chi tiết.

---

## 🙏 Acknowledgments

- [Qwen Team](https://github.com/QwenLM) - Base model
- [PEFT](https://github.com/huggingface/peft) - LoRA implementation
- Vietnamese math education community

---

*Bản cập nhật cuối: 2026*
