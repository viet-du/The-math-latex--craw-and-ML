# 📊 Sơ Đồ Quy Trình Chuyển Đổi Dữ Liệu

## 1. Tổng Quan Quy Trình

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                         QUY TRÌNH CHUYỂN ĐỔI DỮ LIỆU                                │
│                         5-Agent Math Solver Data Pipeline                               │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                          ┌─────────────────────────────────────┐
                          │   NGUỒN DỮ LIỆU THÔ               │
                          │   DATA/datasheet_final_vi3.json     │
                          │   (~1700+ bài toán tiếng Việt)    │
                          └─────────────────┬───────────────────┘
                                            │
                                            ▼
                          ┌─────────────────────────────────────┐
                          │   BƯỚC 1: LOAD DATA                │
                          │   - Đọc JSON file                  │
                          │   - Filter valid entries            │
                          │   - Validate required fields        │
                          └─────────────────┬───────────────────┘
                                            │
                                            ▼
                          ┌─────────────────────────────────────┐
                          │   BƯỚC 2: SPLIT DATASET            │
                          │                                     │
                          │   ┌───────────────────────────────┐ │
                          │   │  Train    │  Val    │  Test │ │
                          │   │   80%    │   10%   │  10%  │ │
                          │   │ (~1360)  │  (~170) │ (~170)│ │
                          │   └───────────────────────────────┘ │
                          └─────────────────┬───────────────────┘
                                            │
                                            ▼
                          ┌─────────────────────────────────────┐
                          │   BƯỚC 3: TRANSFORM CHO TỪNG AGENT │
                          │                                     │
                          │   Mỗi problem → 5 records mới     │
                          │   (agent1, agent2, agent3,         │
                          │    agent4, agent5)                │
                          └─────────────────┬───────────────────┘
                                            │
                          ┌─────────────────┼─────────────────┐
                          │                 │                 │
                          ▼                 ▼                 ▼
              ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
              │    AGENT 1        │ │    AGENT 2        │ │    AGENT 3        │
              │  ┌─────────────┐  │ │  ┌─────────────┐  │ │  ┌─────────────┐  │
              │  │ Transform   │  │ │  │ Transform   │  │ │  │ Transform   │  │
              │  │ for Agent1  │  │ │  │ for Agent2  │  │ │  │ for Agent3  │  │
              │  └─────────────┘  │ │  └─────────────┘  │ │  └─────────────┘  │
              │  Task: Chuẩn hóa │ │  Task: Phân loại │ │  Task: Suy luận  │
              │  Output: Đề chuẩn│ │  Output: Loại bài│ │  Output: Bước giải│
              └───────────────────┘ └───────────────────┘ └───────────────────┘
                          │                 │                 │
                          ▼                 ▼                 ▼
              ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
              │    AGENT 4        │ │    AGENT 5        │ │    (Tiếp tục...) │
              │  ┌─────────────┐  │ │  ┌─────────────┐  │ │                   │
              │  │ Transform   │  │ │  │ Transform   │  │ │                   │
              │  │ for Agent4  │  │ │  │ for Agent5  │  │ │                   │
              │  └─────────────┘  │ │  └─────────────┘  │ │                   │
              │  Task: Trình bày │ │  Task: Xác minh  │ │                   │
              │  Output: Lời giải│ │  Output: Verify  │ │                   │
              └───────────────────┘ └───────────────────┘ └───────────────────┘
                          │                 │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────────────────────────┐
                          │   BƯỚC 4: EXPORT JSONL              │
                          │                                     │
                          │   DATA/5agent_final/                │
                          │   ├── train/                        │
                          │   │   ├── agent1.jsonl              │
                          │   │   ├── agent2.jsonl              │
                          │   │   ├── agent3.jsonl              │
                          │   │   ├── agent4.jsonl              │
                          │   │   └── agent5.jsonl              │
                          │   ├── val/                          │
                          │   └── test/                         │
                          └─────────────────────────────────────┘
```

---

## 2. Chi Tiết Transform Cho Từng Agent

### 2.1 Agent 1: Chuẩn Hóa (Normalization)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENT 1: CHUẨN HÓA                                  │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT (Original Problem):
━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "id": "math_001",
  "problem": "Giải phương trình: x² - 5x + 6 = 0"
}

PROCESSING:
━━━━━━━━━━━
┌─────────────────────────────────────────┐
│ System Prompt (SYSTEM_PROMPTS["agent1"]) │
│ ─────────────────────────────────────── │
│ "Bạn là Agent 1 - Chuẩn hóa bài toán. │
│  Nhiệm vụ: Viết lại bài toán dưới    │
│  dạng LaTeX chuẩn."                    │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Expected Output                        │
│ ────────────────────────────────────── │
│ "Đề chuẩn hóa:                       │
│  $x^2 - 5x + 6 = 0$                  │
│  Dạng: Phương trình bậc 2             │
│  Hệ số: $a=1, b=-5, c=6$"            │
└─────────────────────────────────────────┘

OUTPUT (Transformed Record):
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "id": "math_001_agent1",
  "messages": [
    {"role": "system", "content": "Bạn là Agent 1..."},
    {"role": "user", "content": "Giải phương trình: x² - 5x + 6 = 0"},
    {"role": "assistant", "content": "Đề chuẩn hóa:\n$x^2 - 5x + 6 = 0$\n..."}
  ]
}
```

### 2.2 Agent 2: Phân Loại (Classification)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENT 2: PHÂN LOẠI                                  │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT (Original Problem):
━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "id": "math_001",
  "problem": "Giải phương trình: x² - 5x + 6 = 0",
  "type": "algebra",          // ← Từ metadata
  "difficulty": "easy"       // ← Từ metadata
}

PROCESSING:
━━━━━━━━━━━
┌─────────────────────────────────────────┐
│ System Prompt (SYSTEM_PROMPTS["agent2"]) │
│ ─────────────────────────────────────── │
│ "Bạn là Agent 2 - Phân loại bài toán. │
│  Nhiệm vụ: Xác định loại bài toán.   │
│  Format: [Chủ đề] | [Loại] | [Độ khó]" │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Expected Output                        │
│ ────────────────────────────────────── │
│ "Đại số | Tính toán | Dễ"            │
└─────────────────────────────────────────┘

OUTPUT (Transformed Record):
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "id": "math_001_agent2",
  "messages": [
    {"role": "system", "content": "Bạn là Agent 2..."},
    {"role": "user", "content": "Giải phương trình: x² - 5x + 6 = 0"},
    {"role": "assistant", "content": "Đại số | Tính toán | Dễ"}
  ]
}
```

### 2.3 Agent 3: Suy Luận (Reasoning)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENT 3: SUY LUẬN (Chain-of-Thought)                 │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT (Original Problem with Steps):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "id": "math_001",
  "problem": "Giải phương trình: x² - 5x + 6 = 0",
  "solution_steps": [                        // ← Từ metadata
    "Tính Δ = b² - 4ac = 25 - 24 = 1",
    "Áp dụng công thức: x = (5 ± √1)/2",
    "x₁ = 3, x₂ = 2"
  ]
}

PROCESSING:
━━━━━━━━━━━
┌─────────────────────────────────────────┐
│ System Prompt (SYSTEM_PROMPTS["agent3"]) │
│ ─────────────────────────────────────── │
│ "Bạn là Agent 3 - Suy luận giải toán. │
│  Nhiệm vụ: Giải bài toán từng bước.  │
│  Mỗi bước: (1) Làm gì, (2) Áp dụng   │
│  công thức gì, (3) Kết quả"            │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Expected Output (từ solution_steps)    │
│ ────────────────────────────────────── │
│ "Bước 1: $\Delta = b^2 - 4ac = 1$    │
│ — Tính delta                          │
│                                      │
│ Bước 2: $x = \frac{5 \pm 1}{2}$      │
│ — Áp dụng công thức                  │
│                                      │
│ Bước 3: $x_1 = 3, x_2 = 2$           │
│ — Kết luận"                           │
└─────────────────────────────────────────┘

OUTPUT (Transformed Record):
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "id": "math_001_agent3",
  "messages": [
    {"role": "system", "content": "Bạn là Agent 3..."},
    {"role": "user", "content": "Giải phương trình: x² - 5x + 6 = 0"},
    {"role": "assistant", "content": "Bước 1: $\Delta = ...$\nBước 2: ...\nBước 3: ..."}
  ]
}
```

### 2.4 Agent 4: Trình Bày (Formatter)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENT 4: TRÌNH BÀY                                  │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT (Original Problem with Solution):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "id": "math_001",
  "problem": "Giải phương trình: x² - 5x + 6 = 0",
  "solution_steps": [...],
  "answer": "x = 2 hoặc x = 3"
}

PROCESSING:
━━━━━━━━━━━
┌─────────────────────────────────────────┐
│ System Prompt (SYSTEM_PROMPTS["agent4"]) │
│ ─────────────────────────────────────── │
│ "Bạn là Agent 4 - Trình bày lời giải. │
│  Nhiệm vụ: Viết lời giải hoàn chỉnh. │
│  Format: **Công thức**, **Lời giải**,  │
│  **Đáp số**: \boxed{}"                 │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Expected Output                        │
│ ────────────────────────────────────── │
│ "**Lời giải chi tiết:**              │
│                                      │
│ Bước 1: Tính $\Delta = 1$           │
│ Bước 2: Áp dụng công thức           │
│ Bước 3: Kết luận                     │
│                                      │
│ Vậy đáp án là: \boxed{x = 2 \text{  │
│ hoặc } x = 3}"                       │
└─────────────────────────────────────────┘

OUTPUT (Transformed Record):
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "id": "math_001_agent4",
  "messages": [
    {"role": "system", "content": "Bạn là Agent 4..."},
    {"role": "user", "content": "Giải phương trình: x² - 5x + 6 = 0"},
    {"role": "assistant", "content": "**Lời giải chi tiết:**\n...\n\\boxed{x = 2 \\text{ hoặc } x = 3}"}
  ]
}
```

### 2.5 Agent 5: Xác Minh (Verification)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AGENT 5: XÁC MINH                                    │
└─────────────────────────────────────────────────────────────────────────────┘

INPUT (Original Problem with Answer):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "id": "math_001",
  "problem": "Giải phương trình: x² - 5x + 6 = 0",
  "solution_steps": [...],
  "answer": "x = 2 hoặc x = 3"
}

PROCESSING:
━━━━━━━━━━━
┌─────────────────────────────────────────┐
│ System Prompt (SYSTEM_PROMPTS["agent5"])│
│ ───────────────────────────────────────│
│ "Bạn là Agent 5 - Kiểm tra và xác nhận│
│  đáp án.                               │
│  Nhiệm vụ: Xác minh lời giải cuối.   │
│  Format: Đáp án đúng: \\boxed{}"      │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Expected Output                        │
│ ────────────────────────────────────── │
│ "Đáp án đúng: \boxed{x = 2, 3}"     │
└─────────────────────────────────────────┘

OUTPUT (Transformed Record):
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{
  "id": "math_001_agent5",
  "messages": [
    {"role": "system", "content": "Bạn là Agent 5..."},
    {"role": "user", "content": "Bài toán: ...\nLời giải đề xuất: ...\nĐáp án: x = 2 hoặc x = 3"},
    {"role": "assistant", "content": "Đáp án đúng: \\boxed{x = 2, 3}"}
  ]
}
```

---

## 3. Sơ Đồ Luồng Dữ Liệu Chi Tiết

```
╔═══════════════════════════════════════════════════════════════════════════════════════════╗
║                              LUỒNG DỮ LIỆU CHI TIẾT                                      ║
╠═══════════════════════════════════════════════════════════════════════════════════════════╣

                                    INPUT JSONL
                              datasheet_final_vi3.json
                                         │
                                         ▼
                    ┌────────────────────────────────────────────┐
                    │            JSON LOADER                     │
                    │  - Parse JSON                              │
                    │  - Extract: problem, steps, answer,        │
                    │    type, difficulty                        │
                    └─────────────────────┬──────────────────────┘
                                          │
                                          ▼
                    ┌────────────────────────────────────────────┐
                    │            VALIDATION                      │
                    │  - Check required fields                   │
                    │  - Filter invalid entries                  │
                    │  - Normalize data                          │
                    └─────────────────────┬──────────────────────┘
                                          │
                                          ▼
                              ┌───────────────────────┐
                              │   RANDOM SHUFFLE      │
                              │   seed=42             │
                              └───────────┬───────────┘
                                          │
                                          ▼
                    ┌────────────────────────────────────────────┐
                    │            DATASET SPLIT                   │
                    │                                             │
                    │   ┌─────────┬─────────┬─────────┐           │
                    │   │  TRAIN  │   VAL   │  TEST  │           │
                    │   │   80%   │   10%   │   10%  │           │
                    │   └─────────┴─────────┴─────────┘           │
                    └─────────────────────┬──────────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
                    ▼                     ▼                     ▼
             ┌────────────┐        ┌────────────┐        ┌────────────┐
             │   TRAIN    │        │    VAL     │        │   TEST    │
             │   SPLIT    │        │   SPLIT    │        │   SPLIT    │
             └─────┬──────┘        └─────┬──────┘        └─────┬──────┘
                   │                     │                     │
                   ▼                     ▼                     ▼
    ┌────────────────────────────────────────────────────────────────────────┐
    │                      TRANSFORMATION LOOP                               │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
    │  │ Agent 1    │  │ Agent 2    │  │ Agent 3    │  │ Agent 4    │   │
    │  │ Transform   │  │ Transform   │  │ Transform   │  │ Transform   │   │
    │  │ Function    │  │ Function    │  │ Function    │  │ Function    │   │
    │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
    │         │                │                │                │         │
    │         └────────────────┼────────────────┼────────────────┘         │
    │                          │                │                          │
    │                          ▼                ▼                          │
    │         ┌────────────────────────────────────────┐                  │
    │         │         Agent 5 Transform              │                  │
    │         │         Function                       │                  │
    │         └────────────────────┬───────────────────┘                  │
    │                              │                                      │
    └──────────────────────────────┼──────────────────────────────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
           ▼                       ▼                       ▼
    ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
    │  agent1     │        │  agent2     │        │  agent3     │
    │  records    │        │  records    │        │  records    │
    │  list[]     │        │  list[]     │        │  list[]     │
    └──────┬──────┘        └──────┬──────┘        └──────┬──────┘
           │                       │                       │
           ▼                       ▼                       ▼
    ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
    │ agent1.jsonl│        │ agent2.jsonl│        │ agent3.jsonl│
    │ (Train)     │        │ (Train)     │        │ (Train)     │
    └─────────────┘        └─────────────┘        └─────────────┘
           │                       │                       │
           ▼                       ▼                       ▼
    ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
    │ agent1.jsonl│        │ agent2.jsonl│        │ agent3.jsonl│
    │ (Val)       │        │ (Val)       │        │ (Val)       │
    └─────────────┘        └─────────────┘        └─────────────┘
           │                       │                       │
           ▼                       ▼                       ▼
    ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
    │ agent1.jsonl│        │ agent2.jsonl│        │ agent3.jsonl│
    │ (Test)      │        │ (Test)      │        │ (Test)      │
    └─────────────┘        └─────────────┘        └─────────────┘

╚═══════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 4. Data Flow Animation (Step by Step)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║  STEP 1: READ RAW DATA                                                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

    datasheet_final_vi3.json
    ─────────────────────────
    [
      {
        "id": "math_001",
        "problem": "Giải phương trình: x² - 5x + 6 = 0",
        "answer": "x = 2 hoặc x = 3",
        "type": "algebra",
        "difficulty": "easy",
        "steps": ["Tính Δ", "Áp dụng công thức", "Kết luận"]
      },
      {
        "id": "math_002",
        ...
      },
      ...
    ]
          │
          │  load_jsonl()
          ▼
    ┌─────────────────────────────────┐
    │  raw_data: List[~1700 items]    │
    └─────────────────────────────────┘


╔═══════════════════════════════════════════════════════════════════════════════╗
║  STEP 2: VALIDATE & FILTER                                                ║
╚═══════════════════════════════════════════════════════════════════════════════╝

    ┌─────────────────────────────────┐
    │  VALIDATION CHECKS              │
    ├─────────────────────────────────┤
    │  ✓ id exists?                  │
    │  ✓ problem not empty?           │
    │  ✓ answer exists?              │
    │  ✓ valid JSON structure?        │
    └─────────────────────────────────┘
          │
          ▼
    ┌─────────────────────────────────┐
    │  valid_entries: List[~1700]     │
    └─────────────────────────────────┘


╔═══════════════════════════════════════════════════════════════════════════════╗
║  STEP 3: SPLIT (80/10/10)                                                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝

    ┌─────────────────────────────────┐
    │  random.shuffle(valid_entries)  │
    │           seed=42               │
    └─────────────────────────────────┘
          │
          ▼
    ┌─────────┬─────────┬─────────┐
    │  TRAIN  │   VAL   │  TEST  │
    │   80%   │   10%   │   10%  │
    │ (~1360) │  (~170) │ (~170) │
    └─────────┴─────────┴─────────┘


╔═══════════════════════════════════════════════════════════════════════════════╗
║  STEP 4: TRANSFORM FOR EACH AGENT                                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝

    For each problem in train_data:
    ┌──────────────────────────────────────────────────────────────┐
    │                                                              │
    │   problem: "Giải phương trình: x² - 5x + 6 = 0"          │
    │                                                              │
    │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
    │   │Agent 1  │  │Agent 2  │  │Agent 3  │  │Agent 4  │       │
    │   │Transform│→ │Transform│→ │Transform│→ │Transform│→ ...  │
    │   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
    │        │             │             │             │             │
    │        ▼             ▼             ▼             ▼             │
    │   record1       record2       record3       record4        │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘
          │
          ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  agent_data = {                                           │
    │    "agent1": [record1, record2, ...],  // ~1360 items     │
    │    "agent2": [record1, record2, ...],  // ~1360 items     │
    │    "agent3": [record1, record2, ...],  // ~1360 items     │
    │    "agent4": [record1, record2, ...],  // ~1360 items     │
    │    "agent5": [record1, record2, ...],  // ~1360 items     │
    │  }                                                         │
    └──────────────────────────────────────────────────────────────┘


╔═══════════════════════════════════════════════════════════════════════════════╗
║  STEP 5: EXPORT TO JSONL                                                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝

    ┌──────────────────────────────────────────────────────────────┐
    │  OUTPUT DIRECTORY: DATA/5agent_final/                       │
    └──────────────────────────────────────────────────────────────┘
          │
          ▼
    DATA/5agent_final/
    ├── train/
    │   ├── agent1.jsonl    ← 1360 lines
    │   ├── agent2.jsonl    ← 1360 lines
    │   ├── agent3.jsonl    ← 1360 lines
    │   ├── agent4.jsonl    ← 1360 lines
    │   └── agent5.jsonl    ← 1360 lines
    │
    ├── val/
    │   ├── agent1.jsonl    ← 170 lines
    │   ├── agent2.jsonl    ← 170 lines
    │   ├── agent3.jsonl    ← 170 lines
    │   ├── agent4.jsonl    ← 170 lines
    │   └── agent5.jsonl    ← 170 lines
    │
    └── test/
        ├── agent1.jsonl    ← 170 lines
        ├── agent2.jsonl    ← 170 lines
        ├── agent3.jsonl    ← 170 lines
        ├── agent4.jsonl    ← 170 lines
        └── agent5.jsonl    ← 170 lines
```

---

## 5. So Sánh Input vs Output

```
┌─────────────────────────────────────┬─────────────────────────────────────┐
│           INPUT                     │           OUTPUT                     │
│  (datasheet_final_vi3.json)       │  (5agent_final/*.jsonl)            │
├─────────────────────────────────────┼─────────────────────────────────────┤
│                                     │                                     │
│  {                                 │  {                                  │
│    "id": "math_001",              │    "id": "math_001_agent1",        │
│    "problem": "...",              │    "messages": [                    │
│    "answer": "...",               │      {"role": "system", ...},     │
│    "type": "algebra",            │      {"role": "user", ...},         │
│    "difficulty": "easy",         │      {"role": "assistant", ...}    │
│    "steps": [...]                 │    ]                                │
│  }                                 │  }                                  │
│                                     │                                     │
│  1 record = 1 problem             │  1 record = 1 agent task            │
│                                     │                                     │
│  Total: ~1700 records             │  Total: ~1700 × 5 = ~8500 records  │
│                                     │                                     │
└─────────────────────────────────────┴─────────────────────────────────────┘
```

---

## 6. Scripts Thực Thi

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SCRIPTS CHUYỂN ĐỔI                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────┐     ┌─────────────────────────────────────┐
│  scripts/transform_for_5agent.py    │     │  scripts/convert_datasheet_to_5agent.py│
│  ─────────────────────────────────  │     │  ─────────────────────────────────  │
│                                     │     │                                     │
│  • Input: DATA/clean_dataset_v2/    │     │  • Input: DATA/datasheet_final_vi3.json│
│    └── train.jsonl                  │     │                                     │
│    └── val.jsonl                    │     │  • Output: DATA/5agent_final/        │
│    └── test.jsonl                   │     │    └── train/                        │
│                                     │     │    └── val/                          │
│  • Sử dụng latex_vi_fixes.py       │     │    └── test/                         │
│  • Áp dụng Fix A (diversified      │     │                                     │
│    reasoning templates)             │     │  • Cùng SYSTEM_PROMPTS               │
│  • Áp dụng Fix G (Vietnamese in    │     │                                     │
│    LaTeX substitution)              │     │                                     │
│                                     │     │                                     │
│  ⚡ RECOMMENDED                    │     │  ⚡ Alternative                       │
└─────────────────────────────────────┘     └─────────────────────────────────────┘

Chạy script:
════════════
# Cách 1: transform_for_5agent.py (Khuyến nghị)
python scripts/transform_for_5agent.py

# Cách 2: convert_datasheet_to_5agent.py
python scripts/convert_datasheet_to_5agent.py

Kiểm tra kết quả:
═════════════════
# Đếm số dòng trong mỗi file
wc -l DATA/5agent_final/train/*.jsonl
# Kết quả mong đợi:
# agent1.jsonl: ~1360
# agent2.jsonl: ~1360
# ...
```

---

## 7. Verification Checklist

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VERIFICATION CHECKLIST                                    │
│                    Sau Khi Chuyển Đổi                                       │
└─────────────────────────────────────────────────────────────────────────────┘

[ ] Kiểm tra số lượng records
    ├── Train: ~1360 × 5 = ~6800 records
    ├── Val:   ~170  × 5 = ~850 records
    └── Test:  ~170  × 5 = ~850 records

[ ] Kiểm tra format JSON
    └── Mỗi line là valid JSON object

[ ] Kiểm tra cấu trúc messages
    ├── Có 3 messages: system, user, assistant
    ├── System prompt khớp với inference script
    └── Content không rỗng

[ ] Kiểm tra System Prompts
    ├── Training: scripts/transform_for_5agent.py
    └── Inference: train_model/inference_5agent_kaggle.py
        └── PHẢI GIỐNG NHAU

[ ] Kiểm tra sample đặc biệt
    ├── agent3: reasoning đa dạng (Fix A)
    └── LaTeX Vietnamese: không có placeholder như "một", "bi" trong LaTeX
```

---

*Báo cáo được tạo: 2026-08-14*
