"""
Convert datasheet_final_vi3.json → 5-Agent Training Format
=======================================================
Transform Vietnamese math dataset to chat format for 5-agent fine-tuning.

Output:
    DATA/5agent_final/
    ├── train/agent1.jsonl ... agent5.jsonl
    ├── val/agent1.jsonl ... agent5.jsonl
    └── test/agent1.jsonl ... agent5.jsonl

Usage:
    python scripts/convert_datasheet_to_5agent.py
"""

import json
import hashlib
import random
import sys
from pathlib import Path
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

random.seed(42)

# =============================================================================
# SYSTEM PROMPTS (MUST MATCH BETWEEN TRAIN & INFERENCE)
# =============================================================================

SYSTEM_PROMPTS = {
    "agent1": (
        "Bạn là Agent 1 - Chuẩn hóa bài toán.\n"
        "Nhiệm vụ: Viết lại bài toán dưới dạng LaTeX chuẩn.\n"
        "QUY TẮC:\n"
        "- Xuất MỖI bài toán đã chuẩn hóa, KHÔNG giải\n"
        "- Dùng \\(...) cho inline math, \\[...\\] cho display math\n"
        "- Giữ nguyên ý nghĩa toán học\n"
        "- Tiếng Việt cho phần text"
    ),
    "agent2": (
        "Bạn là Agent 2 - Phân loại bài toán.\n"
        "Nhiệm vụ: Xác định loại bài toán.\n"
        "QUY TẮC:\n"
        "- Xuất đúng 1 dòng theo format: [Chủ đề] | [Loại] | [Độ khó]\n"
        "- Ví dụ: Phân số | Tính toán | Trung bình\n"
        "- Chủ đề: Phân số, Hình học, Đại số, Tỉ lệ, Phần trăm, Đạo hàm, Xác suất\n"
        "- Loại: Tính toán, Chứng minh, Ứng dụng\n"
        "- Độ khó: Dễ, Trung bình, Khó"
    ),
    "agent3": (
        "Bạn là Agent 3 - Suy luận giải toán.\n"
        "Nhiệm vụ: Giải bài toán từng bước.\n"
        "QUY TẮC:\n"
        "- Mỗi bước: (1) Làm gì, (2) Áp dụng công thức gì, (3) Kết quả\n"
        "- Dùng tiếng Việt hoàn toàn cho giải thích\n"
        "- Dùng LaTeX cho công thức toán học\n"
        "- Viết rõ ràng, logic từng bước"
    ),
    "agent4": (
        "Bạn là Agent 4 - Trình bày lời giải hoàn chỉnh.\n"
        "Nhiệm vụ: Viết lời giải hoàn chỉnh, chuyên nghiệp.\n"
        "QUY TẮC:\n"
        "- Viết các bước theo thứ tự logic\n"
        "- Mỗi bước: (1) Ghi công thức, (2) Thay số, (3) Tính toán, (4) Kết quả\n"
        "- Cuối cùng phải có đáp án trong \\boxed{...}\n"
        "- Dùng tiếng Việt cho toàn bộ text\n"
        "- Dùng LaTeX cho công thức"
    ),
    "agent5": (
        "Bạn là Agent 5 - Kiểm tra và xác nhận đáp án.\n"
        "Nhiệm vụ: Xác minh lời giải có đúng không.\n"
        "QUY TẮC:\n"
        "- Đọc lại bài toán và đáp án đề xuất\n"
        "- Kiểm tra: (1) Đáp án có thỏa mãn bài toán không, (2) Có lỗi tính toán không\n"
        "- Nếu đúng: xuất 'Đáp án đúng: \\boxed{đáp án}'\n"
        "- Nếu sai: xuất 'Sai rồi. Đáp án đúng là: \\boxed{đáp án mới}'\n"
        "- Dùng tiếng Việt hoàn toàn"
    ),
}


# =============================================================================
# AGENT 3 FALLBACK POOL (diversified reasoning templates)
# =============================================================================

AGENT3_REASONING_TEMPLATES = {
    "algebra": [
        "Bước 1: Xác định phương trình cần giải.\n"
        "Bước 2: Chuyển các hạng tử về cùng một vế.\n"
        "Bước 3: Rút gọn và tìm nghiệm.\n"
        "Bước 4: Kiểm tra nghiệm bằng cách thế vào phương trình ban đầu.",
        "Bước 1: Nhận dạng dạng bài toán đại số.\n"
        "Bước 2: Áp dụng các quy tắc biến đổi tương đương.\n"
        "Bước 3: Giải phương trình bậc nhất hoặc bậc hai.\n"
        "Bước 4: Kết luận nghiệm và kiểm tra.",
    ],
    "geometry": [
        "Bước 1: Vẽ hình và xác định các yếu tố đã biết.\n"
        "Bước 2: Tìm mối liên hệ giữa các yếu tố.\n"
        "Bước 3: Áp dụng định lý hoặc công thức phù hợp.\n"
        "Bước 4: Tính toán và kiểm tra kết quả.",
        "Bước 1: Đọc kỹ đề bài và xác định yêu cầu.\n"
        "Bước 2: Chọn phương pháp phù hợp (tam giác đồng dạng, Pitago, ...).\n"
        "Bước 3: Thực hiện các phép tính cần thiết.\n"
        "Bước 4: Trả lời và kiểm tra lại.",
    ],
    "calculus": [
        "Bước 1: Xác định loại bài toán giải tích.\n"
        "Bước 2: Nhận dạng công thức đạo hàm hoặc tích phân.\n"
        "Bước 3: Áp dụng các quy tắc tính đạo hàm/tích phân.\n"
        "Bước 4: Rút gọn và đưa ra kết quả.",
        "Bước 1: Xác định hàm số cần tính đạo hàm hoặc tích phân.\n"
        "Bước 2: Chọn công thức phù hợp.\n"
        "Bước 3: Thực hiện các bước tính toán.\n"
        "Bước 4: Kiểm tra kết quả bằng cách đạo hàm ngược.",
    ],
    "default": [
        "Bước 1: Đọc và hiểu yêu cầu của bài toán.\n"
        "Bước 2: Xác định các dữ kiện đã cho.\n"
        "Bước 3: Áp dụng phương pháp giải phù hợp.\n"
        "Bước 4: Tính toán và đưa ra kết quả cuối cùng.",
        "Bước 1: Phân tích bài toán để xác định hướng giải.\n"
        "Bước 2: Lựa chọn công thức và phương pháp phù hợp.\n"
        "Bước 3: Thực hiện các bước biến đổi và tính toán.\n"
        "Bước 4: Kiểm tra và kết luận đáp án.",
    ],
}


def get_agent3_reasoning(category: str, row_id: str) -> str:
    """Get diversified reasoning template based on category."""
    templates = AGENT3_REASONING_TEMPLATES.get(category, AGENT3_REASONING_TEMPLATES["default"])
    idx = abs(hash(row_id)) % len(templates)
    return templates[idx]


# =============================================================================
# CATEGORY MAPPING
# =============================================================================

CATEGORY_MAP = {
    "algebra": "Đại số",
    "geometry": "Hình học",
    "calculus": "Giải tích",
    "fraction": "Phân số",
    "percentage": "Phần trăm",
    "ratio": "Tỉ lệ",
    "motion": "Chuyển động",
    "probability": "Xác suất",
    "statistics": "Thống kê",
    "machine_learning": "Học máy",
    "deep_learning": "Học sâu",
    "linear_algebra": "Đại số tuyến tính",
    "data_structures_algorithms": "Cấu trúc dữ liệu & Giải thuật",
    "number_theory": "Số học",
    "combinatorics": "Tổ hợp",
    "logic": "Logic",
    "graph_theory": "Lý thuyết đồ thị",
}

DIFFICULTY_MAP = {
    "easy": "Dễ",
    "medium": "Trung bình",
    "hard": "Khó",
    "expert": "Chuyên gia",
    "easy": "Dễ",
    "medium": "Trung bình",
    "hard": "Khó",
}


# =============================================================================
# TRANSFORMATION FUNCTIONS
# =============================================================================

def transform_for_agent1(entry: dict) -> dict:
    """Transform for Agent 1: Normalize problem"""
    problem = entry.get("input", entry.get("instruction", ""))
    original = entry.get("canonical_form", entry.get("input", ""))
    
    return {
        "id": f"{entry['id']}_agent1",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["agent1"]},
            {"role": "user", "content": original},
            {"role": "assistant", "content": f"Bài toán chuẩn hóa:\n{original}"}
        ]
    }


def transform_for_agent2(entry: dict) -> dict:
    """Transform for Agent 2: Classify problem"""
    problem = entry.get("input", "")
    category = entry.get("type", "default")
    difficulty = entry.get("difficulty", "medium")
    
    category_vn = CATEGORY_MAP.get(category, category.replace("_", " ").title())
    difficulty_vn = DIFFICULTY_MAP.get(difficulty, "Trung bình")
    
    classification = f"{category_vn} | Tính toán | {difficulty_vn}"
    
    return {
        "id": f"{entry['id']}_agent2",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["agent2"]},
            {"role": "user", "content": problem},
            {"role": "assistant", "content": classification}
        ]
    }


def transform_for_agent3(entry: dict) -> dict:
    """Transform for Agent 3: Reason step by step"""
    problem = entry.get("input", "")
    steps = entry.get("steps", [])
    category = entry.get("type", "default")
    
    if steps:
        reasoning = "\n\n".join([f"Bước {i+1}: {step}" for i, step in enumerate(steps[:5])])
    else:
        reasoning = get_agent3_reasoning(category, entry["id"])
    
    return {
        "id": f"{entry['id']}_agent3",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["agent3"]},
            {"role": "user", "content": problem},
            {"role": "assistant", "content": reasoning}
        ]
    }


def transform_for_agent4(entry: dict) -> dict:
    """Transform for Agent 4: Full solution with boxed answer"""
    problem = entry.get("input", "")
    steps = entry.get("steps", [])
    answer = entry.get("output", "")
    
    solution = "**Lời giải chi tiết:**\n\n"
    
    if steps:
        for i, step in enumerate(steps[:5]):
            solution += f"Bước {i+1}: {step}\n\n"
    else:
        solution += "Thực hiện các phép tính cần thiết để giải bài toán.\n\n"
    
    # Clean answer for boxed
    answer_clean = str(answer).strip().strip("$").strip("\\boxed{").strip("}")
    if answer_clean:
        solution += f"Vậy đáp án là: \\boxed{{{answer_clean}}}"
    else:
        solution += "Vậy đáp án là: \\boxed{0}"
    
    return {
        "id": f"{entry['id']}_agent4",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["agent4"]},
            {"role": "user", "content": problem},
            {"role": "assistant", "content": solution}
        ]
    }


def transform_for_agent5(entry: dict) -> dict:
    """Transform for Agent 5: Verify answer"""
    problem = entry.get("input", "")
    answer = entry.get("output", "")
    steps = entry.get("steps", [])
    
    # Build the proposed solution
    proposed = f"Bài toán: {problem}\n\n"
    if steps:
        proposed += "Lời giải đề xuất:\n"
        for step in steps[:3]:
            proposed += f"- {step}\n"
    proposed += f"\nĐáp án đề xuất: {answer}"
    
    # Clean answer
    answer_clean = str(answer).strip().strip("$").strip("\\boxed{").strip("}")
    verification = f"Đáp án đúng: \\boxed{{{answer_clean}}}"
    
    return {
        "id": f"{entry['id']}_agent5",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["agent5"]},
            {"role": "user", "content": proposed},
            {"role": "assistant", "content": verification}
        ]
    }


# =============================================================================
# MAIN
# =============================================================================

def split_dataset(data: list, train_ratio: float = 0.8, val_ratio: float = 0.1) -> tuple:
    """Split data into train/val/test."""
    random.shuffle(data)
    n = len(data)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)
    
    train = data[:train_end]
    val = data[train_end:val_end]
    test = data[val_end:]
    
    return train, val, test


def main():
    print("=" * 70)
    print("CONVERT DATASHEET → 5-AGENT TRAINING FORMAT")
    print("=" * 70)
    print()
    
    # Load datasheet
    print("[1/4] Loading datasheet...")
    with open("DATA/datasheet_final_vi3.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    print(f"      Total entries: {len(raw_data)}")
    
    # Filter valid entries
    print("[2/4] Filtering valid entries...")
    valid_entries = []
    for entry in raw_data:
        entry_id = entry.get("id", "")
        if not entry_id:
            continue
        valid_entries.append(entry)
    print(f"      Valid entries: {len(valid_entries)}")
    
    # Split data
    print("[3/4] Splitting data (80/10/10)...")
    train_data, val_data, test_data = split_dataset(valid_entries)
    print(f"      Train: {len(train_data)}")
    print(f"      Val:   {len(val_data)}")
    print(f"      Test:  {len(test_data)}")
    
    # Transform for each split
    print("[4/4] Transforming for 5 agents...")
    
    for split_name, split_data in [("train", train_data), ("val", val_data), ("test", test_data)]:
        print(f"\n   Processing {split_name}...")
        
        # Initialize output
        agent_data = {f"agent{i}": [] for i in range(1, 6)}
        
        for entry in split_data:
            try:
                agent_data["agent1"].append(transform_for_agent1(entry))
                agent_data["agent2"].append(transform_for_agent2(entry))
                agent_data["agent3"].append(transform_for_agent3(entry))
                agent_data["agent4"].append(transform_for_agent4(entry))
                agent_data["agent5"].append(transform_for_agent5(entry))
            except Exception as e:
                print(f"   ⚠️ Error with {entry.get('id', 'unknown')}: {e}")
                continue
        
        # Export
        output_dir = Path(f"DATA/5agent_final/{split_name}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for agent_id, data in agent_data.items():
            filepath = output_dir / f"{agent_id}.jsonl"
            with open(filepath, 'w', encoding='utf-8') as f:
                for item in data:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
            print(f"      {agent_id}: {len(data)} samples")
    
    print()
    print("=" * 70)
    print("✅ CONVERSION COMPLETE!")
    print("=" * 70)
    print()
    print("📁 Output: DATA/5agent_final/")
    print()
    print("⚠️ IMPORTANT: Verify prompts match between:")
    print("   - DATA/5agent_final/ (training)")
    print("   - train_model/inference_5agent_kaggle.py (inference)")


if __name__ == "__main__":
    main()
