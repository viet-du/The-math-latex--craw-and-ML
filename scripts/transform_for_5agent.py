"""
Transform Clean Dataset → 5-Agent Training Format
=============================================
Convert problems to chat format for each agent.

Output:
    DATA/5agent_final/
    ├── agent1_train.jsonl
    ├── agent1_val.jsonl
    ├── agent1_test.jsonl
    └── ...

Usage:
    python scripts/transform_for_5agent.py
"""

import json
import hashlib
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# FIX A + FIX G: Pull the canonical diversified-template helper and the
# LaTeX Vietnamese-placeholder substitution from the shared module so
# agent3 is no longer mode-collapsed (Fix A) and any LaTeX-bearing text
# written into the assistant message has its `một`/`bi`/`trái`/`phải`
# placeholders cleaned up (Fix G). The pool / function / regex live in
# `scripts/convert_datasheet_to_agents.py` and are re-exported by
# `scripts/latex_vi_fixes.py` -- we never duplicate them here.
from latex_vi_fixes import (
    _diversified_agent3_fallback_lines,
    substitute_vietnamese_in_latex,
)


# =============================================================================
# SYSTEM PROMPTS - FULLY VIETNAMESE (MUST MATCH BETWEEN TRAIN & INFERENCE)
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
        "- Nếu đúng: xuất 'Dap an dung: \\boxed{đáp án}'\n"
        "- Nếu sai: xuất 'Sai roi. Dap an dung la: \\boxed{đáp án mới}'\n"
        "- Dùng tiếng Việt hoàn toàn"
    ),
}


# =============================================================================
# TRANSFORMATION FUNCTIONS
# =============================================================================

def transform_for_agent1(problem_entry):
    """Transform for Agent 1: Normalize problem"""
    problem = problem_entry['problem']
    answer = problem_entry.get('answer', '')
    
    return {
        "id": f"{problem_entry['id']}_agent1",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["agent1"]},
            {"role": "user", "content": problem},
            {"role": "assistant", "content": f"Bai toan chuan hoa:\n{problem}"}
        ]
    }


def transform_for_agent2(problem_entry):
    """Transform for Agent 2: Classify problem"""
    problem = problem_entry['problem']
    category = problem_entry.get('category', 'unknown')
    difficulty = problem_entry.get('difficulty', 'medium')
    
    # Map category to Vietnamese
    category_map = {
        'algebra': 'Đại số',
        'geometry': 'Hình học',
        'calculus': 'Giải tích',
        'fraction': 'Phân số',
        'percentage': 'Phần trăm',
        'ratio': 'Tỉ lệ',
        'motion': 'Chuyển động',
        'probability': 'Xác suất',
        'statistics': 'Thống kê',
        'machine_learning': 'Học máy',
        'deep_learning': 'Học sâu',
        'linear_algebra': 'Đại số tuyến tính',
    }
    
    category_vn = category_map.get(category, category.title())
    difficulty_vn = {'easy': 'Dễ', 'medium': 'Trung bình', 'hard': 'Khó', 'expert': 'Chuyên gia'}.get(difficulty, 'Trung bình')
    
    classification = f"{category_vn} | Tính toán | {difficulty_vn}"
    
    return {
        "id": f"{problem_entry['id']}_agent2",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["agent2"]},
            {"role": "user", "content": problem},
            {"role": "assistant", "content": classification}
        ]
    }


def transform_for_agent3(problem_entry):
    """Transform for Agent 3: Reason step by step"""
    problem = problem_entry['problem']
    steps = problem_entry.get('solution_steps', [])
    # FIX A: derive a stable per-row index from the row's id so the
    # diversified fallback is deterministic across regenerations. The
    # pool is keyed on math_type (looked up from `category`); we fall
    # back to `default` if the row has no category metadata.
    row_id = str(problem_entry.get('id', 'unknown'))
    example_idx = abs(hash(row_id))
    category = problem_entry.get('category', 'default')

    if not steps:
        # FIX A: rotate through the math-type fallback pool instead of
        # emitting the same static paragraph for every empty-steps row.
        # In the original `5agent_final/` dataset this static string
        # accounted for 64.87% of agent3 rows, which biased the LoRA
        # toward pure memorisation. Now we get a per-row template
        # selected from the pool.
        lines = _diversified_agent3_fallback_lines(category, example_idx)
        reasoning = "\n".join(lines)
    else:
        reasoning = "\n\n".join([f"Bước {i+1}: {step}" for i, step in enumerate(steps[:5])])

    # FIX G: clean up any Vietnamese placeholders (`một`, `bi`, `trái`,
    # `phải`) that may leak into the agent3 reasoning text from the
    # dataset templates (they only matter inside `$...$` / `$$...$$`
    # blocks, but we run the helper unconditionally -- it leaves plain
    # Vietnamese text outside LaTeX untouched).
    reasoning = substitute_vietnamese_in_latex(reasoning)

    return {
        "id": f"{problem_entry['id']}_agent3",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["agent3"]},
            {"role": "user", "content": problem},
            {"role": "assistant", "content": reasoning}
        ]
    }


def transform_for_agent4(problem_entry):
    """Transform for Agent 4: Full solution with boxed answer"""
    problem = problem_entry['problem']
    steps = problem_entry.get('solution_steps', [])
    answer = problem_entry.get('answer', '')
    
    solution = "**Lời giải chi tiết:**\n\n"
    
    if steps:
        for i, step in enumerate(steps[:5]):
            solution += f"Bước {i+1}: {step}\n\n"
    else:
        solution += "Thực hiện các phép tính cần thiết để giải bài toán.\n\n"
    
    # Clean answer for boxed
    answer_clean = str(answer).strip()
    if answer_clean:
        solution += f"Vậy đáp án là: \\boxed{{{answer_clean}}}"
    else:
        solution += "Vậy đáp án là: \\boxed{0}"

    # FIX G: substitute Vietnamese placeholders inside LaTeX blocks
    # (boxed and any `$...$` math that may sneak into `solution`).
    solution = substitute_vietnamese_in_latex(solution)

    return {
        "id": f"{problem_entry['id']}_agent4",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["agent4"]},
            {"role": "user", "content": problem},
            {"role": "assistant", "content": solution}
        ]
    }


def transform_for_agent5(problem_entry):
    """Transform for Agent 5: Verify answer"""
    problem = problem_entry['problem']
    answer = problem_entry.get('answer', '')
    steps = problem_entry.get('solution_steps', [])
    
    # Build the proposed solution
    proposed = f"Bài toán: {problem}\n\n"
    if steps:
        proposed += "Lời giải đề xuất:\n"
        for step in steps[:3]:
            proposed += f"- {step}\n"
    proposed += f"\nĐáp án đề xuất: {answer}"
    
    verification = f"Dap an dung: \\boxed{{{answer}}}"
    # FIX G: clean up any Vietnamese placeholders inside LaTeX.
    verification = substitute_vietnamese_in_latex(verification)

    return {
        "id": f"{problem_entry['id']}_agent5",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS["agent5"]},
            {"role": "user", "content": proposed},
            {"role": "assistant", "content": verification}
        ]
    }


# =============================================================================
# MAIN TRANSFORMATION
# =============================================================================

def load_jsonl(filepath):
    """Load JSONL file"""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def main():
    print("=" * 70)
    print("TRANSFORM FOR 5-AGENT TRAINING")
    print("=" * 70)
    print()
    
    # Load data
    print("📦 Loading clean dataset...")
    train_data = load_jsonl("DATA/clean_dataset_v2/train.jsonl")
    val_data = load_jsonl("DATA/clean_dataset_v2/val.jsonl")
    test_data = load_jsonl("DATA/clean_dataset_v2/test.jsonl")
    
    print(f"   Train: {len(train_data)}")
    print(f"   Val:   {len(val_data)}")
    print(f"   Test:  {len(test_data)}")
    print()
    
    # Transform for each split
    for split_name, split_data in [("train", train_data), ("val", val_data), ("test", test_data)]:
        print(f"🔄 Processing {split_name}...")
        
        # Initialize output
        agent_data = {f"agent{i}": [] for i in range(1, 6)}
        
        for entry in split_data:
            try:
                # Transform for each agent
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
            print(f"   {agent_id}: {len(data)} samples")
    
    print()
    print("=" * 70)
    print("✅ TRANSFORMATION COMPLETE!")
    print("=" * 70)
    print()
    print("📁 Output: DATA/5agent_final/")
    print()
    print("⚠️ IMPORTANT: Verify prompts match between:")
    print("   - DATA/5agent_final/ (training)")
    print("   - train_model/inference_vietnamese.py (inference)")


if __name__ == "__main__":
    main()
