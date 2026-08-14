# KẾ HOẠCH HOÀN CHỈNH: Vietnamese Math Solver Pipeline

## MỤC TIÊU
- **Input**: Bài toán tiếng Việt
- **Output**: Lời giải từng bước bằng tiếng Việt (có `\boxed{}`)

---

## SƠ ĐỒ PIPELINE MỚI

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           PIPELINE TỔNG QUAN                                 │
└──────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   BƯỚC 1    │───▶│   BƯỚC 2    │───▶│   BƯỚC 3    │───▶│   BƯỚC 4    │
│ DATA (Input) │    │ TRANSFORM   │    │   TRAIN     │    │  INFERENCE  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                  │                  │                  │
      ▼                  ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ datasheet   │    │ Chat format │    │  5 LoRA     │    │  Solve +    │
│ .json       │    │ + Prompts   │    │  Adapters   │    │  Display    │
│ (raw data)  │    │ VIỆT NAM    │    │  (checkpts) │    │  VIỆT NAM   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## BƯỚC 1: CHUẨN BỊ DATA

### 1.1 Nguồn Data
- **File**: `DATA/datasheet.json`
- **Format hiện tại**: JSON với `problem`, `solution`, `answer`
- **Cần kiểm tra**: 
  - [ ] Encoding UTF-8
  - [ ] Đủ 500-1000 bài toán đa dạng
  - [ ] Có solution từng bước

### 1.2 Yêu cầu Data cho 5-Agent

| Agent | Input | Output |
|-------|-------|--------|
| Agent1 | Bài toán tiếng Việt thô | Bài toán chuẩn hóa LaTeX |
| Agent2 | Bài toán đã chuẩn | Phân loại: chủ đề, độ khó |
| Agent3 | Bài toán + phân loại | Suy luận từng bước |
| Agent4 | Các bước suy luận | Lời giải hoàn chỉnh + `\boxed{}` |
| Agent5 | Lời giải | Verify + xác nhận `\boxed{}` |

### 1.3 Cấu trúc Data Mẫu

```json
{
  "id": "math_001",
  "problem": "Một người có 50 quả táo. Bán đi 3/5 số táo. Hỏi còn lại bao nhiêu quả?",
  "solution_steps": [
    "Tìm số táo đã bán: 50 × 3/5 = 30 quả",
    "Số táo còn lại: 50 - 30 = 20 quả"
  ],
  "final_answer": "20"
}
```

---

## BƯỚC 2: TRANSFORM DATA → TRAINING FORMAT

### 2.1 System Prompts (BẮT BUỘC TIẾNG VIỆT)

```python
PROMPTS = {
    "agent1": (
        "Bạn là Agent 1 - Chuẩn hóa bài toán.\n"
        "Nhiệm vụ: Viết lại bài toán dưới dạng LaTeX chuẩn.\n"
        "QUY TẮC:\n"
        "- Xuất MỖI bài toán đã chuẩn hóa, KHÔNG giải\n"
        "- Dùng \\(...) cho inline math, \\[...\\] cho display math\n"
        "- Giữ nguyên ý nghĩa toán học"
    ),
    "agent2": (
        "Bạn là Agent 2 - Phân loại bài toán.\n"
        "Nhiệm vụ: Xác định loại bài toán.\n"
        "QUY TẮC:\n"
        "- Xuất 1 dòng: [Chủ đề] | [Loại] | [Độ khó]\n"
        "- Ví dụ: Phân số | Tính toán | Trung bình"
    ),
    "agent3": (
        "Bạn là Agent 3 - Suy luận giải toán.\n"
        "Nhiệm vụ: Giải bài toán từng bước.\n"
        "QUY TẮC:\n"
        "- Mỗi bước: làm gì → tại sao → kết quả\n"
        "- Dùng tiếng Việt hoàn toàn\n"
        "- Dùng LaTeX cho công thức"
    ),
    "agent4": (
        "Bạn là Agent 4 - Trình bày lời giải.\n"
        "Nhiệm vụ: Viết lời giải hoàn chỉnh.\n"
        "QUY TẮC:\n"
        "- Các bước theo thứ tự logic\n"
        "- Cuối cùng: \\boxed{đáp án}\n"
        "- Dùng tiếng Việt"
    ),
    "agent5": (
        "Bạn là Agent 5 - Kiểm tra đáp án.\n"
        "Nhiệm vụ: Xác minh đáp án.\n"
        "QUY TẮC:\n"
        "- Kiểm tra: đúng/sai, lỗi tính toán\n"
        "- Xuất: 'Đúng: \\boxed{đáp án}' hoặc 'Sai: \\boxed{đáp án mới}'"
    ),
}
```

### 2.2 Chat Format cho Training

```json
{
  "messages": [
    {"role": "system", "content": "Bạn là Agent 1 - Chuẩn hóa..."},
    {"role": "user", "content": "Một người có 50 quả táo..."},
    {"role": "assistant", "content": "Bài toán chuẩn hóa:\\[50 \\text{ quả táo}, \\frac{3}{5} \\text{ đã bán}\\]"}
  ]
}
```

### 2.3 Tokenization (QUAN TRỌNG!)

```python
def format_for_training(messages, tokenizer):
    # ⚠️ add_generation_prompt=False vì messages đã có đủ
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False  # CRITICAL!
    )
    return prompt
```

---

## BƯỚC 3: TRAINING

### 3.1 Cấu hình Training

```python
TRAINING_CONFIG = {
    "model_name": "Qwen/Qwen2.5-Math-7B-Instruct",
    "lora_rank": 64,
    "lora_alpha": 128,
    "lora_dropout": 0.05,
    "learning_rate": 2e-4,
    "epochs": 3-5,
    "batch_size": 4,
    "max_seq_length": 2048,
    "warmup_steps": 100,
    "lr_scheduler": "cosine",
}
```

### 3.2 Training Loop

```
For mỗi agent (1-5):
    1. Load base model Qwen2.5-Math-7B
    2. Load data_{agent}.jsonl
    3. Apply LoRA adapter
    4. Train với config trên
    5. Save adapter → outputs/agent{1-5}/
```

### 3.3 Validation

- [ ] Chạy inference trên tập val
- [ ] Kiểm tra output có tiếng Việt không
- [ ] Kiểm tra `\boxed{}` có đúng format không
- [ ] Tính accuracy trên các bài toán có đáp án

---

## BƯỚC 4: INFERENCE

### 4.1 Inference Flow

```python
def solve_math_vietnamese(problem):
    # 1. Agent 1: Chuẩn hóa
    normalized = agent1(problem)
    
    # 2. Agent 2: Phân loại
    classification = agent2(normalized)
    
    # 3. Agent 3: Suy luận
    reasoning = agent3(normalized, classification)
    
    # 4. Agent 4: Trình bày
    solution = agent4(reasoning)
    
    # 5. Agent 5: Verify
    verified = agent5(solution)
    
    return extract_boxed(verified)
```

### 4.2 Generation Config (INFERENCE)

```python
GENERATION_CONFIG = {
    "max_new_tokens": 512,
    "do_sample": False,      # Greedy cho toán
    "temperature": None,     # Không cần
    "top_p": None,
    "pad_token_id": tokenizer.eos_token_id,
}
```

### 4.3 Prompt cho Inference (GIỐNG HỆT TRAINING!)

```python
INFERENCE_PROMPTS = {
    "agent1": "Bạn là Agent 1 - Chuẩn hóa bài toán...",
    "agent2": "Bạn là Agent 2 - Phân loại bài toán...",
    "agent3": "Bạn là Agent 3 - Suy luận giải toán...",
    "agent4": "Bạn là Agent 4 - Trình bày lời giải...",
    "agent5": "Bạn là Agent 5 - Kiểm tra đáp án...",
}
```

---

## CHECKLIST TRƯỚC KHI CHẠY

### Data
- [ ] `datasheet.json` có 500+ bài toán tiếng Việt
- [ ] Mỗi bài có `problem`, `solution_steps`, `final_answer`
- [ ] Data đã shuffle, split train/val (80/20)

### Training Scripts
- [ ] Prompts hoàn toàn tiếng Việt
- [ ] `add_generation_prompt=False` trong tokenization
- [ ] LoRA config đúng
- [ ] Gradient checkpointing nếu OOM

### Inference
- [ ] Prompts khớp 100% với training
- [ ] Load đúng adapters cho từng agent
- [ ] Extract `\boxed{}` từ output cuối

---

## CÁC LỖI THƯỜNG GẶP & CÁCH FIX

| Lỗi | Nguyên nhân | Fix |
|------|-------------|-----|
| Output tiếng Anh | Prompts không khớp | Dùng prompts tiếng Việt |
| Model lặp | `add_generation_prompt=True` training | Đổi thành `False` |
| Greedy quá cứng | `do_sample=False` + temp=0 | Giữ `do_sample=False` cho toán |
| Token quá ngắn | `max_tokens=384` | Tăng lên 512+ |
| OOM | Batch size quá lớn | Giảm batch, gradient checkpoint |

---

## THỨ TỰ THỰC HIỆN

```
1. [ ] Kiểm tra và clean data (datasheet.json)
2. [ ] Viết script transform data → chat format
3. [ ] Fix training script (prompts + tokenization)
4. [ ] Train 5 agents
5. [ ] Validate trên tập val
6. [ ] Fix inference script (prompts khớp training)
7. [ ] Test end-to-end
8. [ ] Fine-tune nếu cần
```

---

## FILE CẦN TẠO/SỬA

| File | Action | Mục đích |
|------|--------|----------|
| `DATA/datasheet.json` | Kiểm tra | Raw data |
| `scripts/transform_data.py` | Tạo mới | Convert → chat format |
| `train_model/qwen25_math_5agent_lora_kaggle.py` | Sửa | Training script |
| `train_model/inference_5agent_kaggle.py` | Sửa | Inference script |

---

## ĐÁNH GIÁ KẾT QUẢ

### Metrics
- **Accuracy**: % đáp án `\boxed{}` đúng
- **Language**: % output tiếng Việt
- **Format**: % có `\boxed{}` đúng format
- **Step Quality**: Đánh giá chủ quan từng bước

### Baseline
- Trước fix: Model output không đúng ngôn ngữ, thiếu `\boxed{}`
- Sau fix: Output tiếng Việt, có `\boxed{answer}`

---

**Ngày tạo**: 2026-08-05  
**Người tạo**: Data Science Team
