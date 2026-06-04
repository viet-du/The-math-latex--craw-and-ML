#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter
from typing import Optional


DEFAULT_SYSTEM_PROMPT = (
    "Bạn là một giáo viên Toán giỏi, giải bài chi tiết từng bước bằng tiếng Việt. "
    "Mỗi bước tính toán đều ghi rõ phép tính và kết quả trung gian. "
    "Trình bày công thức bằng LaTeX chuẩn. "
    "Cuối cùng ghi rõ đáp số trong khung \\boxed{}."
)


ENGLISH_PROMPT_REWRITES = [
    ("Apply the given mathematical formula", "Áp dụng công thức toán học sau và giải thích từng bước bằng tiếng Việt"),
    ("Apply trigonometric identity", "Áp dụng hằng đẳng thức lượng giác và trình bày từng bước bằng tiếng Việt"),
    ("Evaluate the integral using standard formula", "Tính tích phân theo công thức chuẩn và trình bày từng bước bằng tiếng Việt"),
    ("Compute gradient for optimization algorithm", "Tính gradient cho thuật toán tối ưu và trình bày từng bước bằng tiếng Việt"),
    ("Apply matrix gradient rule", "Áp dụng quy tắc gradient ma trận và trình bày từng bước bằng tiếng Việt"),
    ("Apply set-theoretic operation", "Áp dụng phép toán tập hợp và trình bày từng bước bằng tiếng Việt"),
    ("Apply statistical formula to data", "Áp dụng công thức thống kê cho dữ liệu và trình bày từng bước bằng tiếng Việt"),
]


TEXT_REPLACEMENTS = {
    "nàa": "này",
    "nàm": "này",
    "hãa": "hãy",
    "1ằng 2ách": "bằng cách",
    "2ách": "cách",
    "đặ2 trưng": "đặc trưng",
    "đặ2": "đặc",
    "phương trình đặ2": "phương trình đặc",
}


ONLY_FINAL_PATTERNS = [
    (
        re.compile(r"Giải bài toán ([^\n.]+?) này và chỉ xuất công thức cuối cùng đúng\.", re.I),
        r"Giải bài toán \1 này bằng tiếng Việt, trình bày từng bước và kết luận bằng LaTeX trong \\boxed{}.",
    ),
    (
        re.compile(r"Viết đáp án ngắn gọn dưới dạng LaTeX chuẩn cho yêu cầu:", re.I),
        "Giải chi tiết bằng tiếng Việt yêu cầu:",
    ),
]


def get_message(messages: list[dict], role: str) -> Optional[str]:
    found = [m.get("content") for m in messages if m.get("role") == role and m.get("content")]
    return found[-1] if found else None


def extract_last_boxed_balanced(text: str) -> Optional[str]:
    key = r"\boxed{"
    idx = text.rfind(key)
    if idx == -1:
        return None
    start = idx + len(key)
    depth = 1
    buf = []
    for ch in text[start:]:
        if ch == "{":
            depth += 1
            buf.append(ch)
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return "".join(buf).strip()
            buf.append(ch)
        else:
            buf.append(ch)
    return None


def balanced_latex_braces(text: str) -> bool:
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def balanced_dollars(text: str) -> bool:
    count = 0
    for i, ch in enumerate(text):
        if ch == "$" and (i == 0 or text[i - 1] != "\\"):
            count += 1
    return count % 2 == 0


def normalize_space(text: str) -> str:
    return " ".join((text or "").split())


def normalize_formula(text: str) -> str:
    return normalize_space(text).replace(" ", "")


def clean_text(text: str) -> str:
    if not text:
        return ""
    for old, new in TEXT_REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.strip()


def rewrite_user_prompt(user: str) -> tuple[str, bool]:
    user = clean_text(user)
    changed = False
    for pattern, replacement in ONLY_FINAL_PATTERNS:
        new_user = pattern.sub(replacement, user)
        if new_user != user:
            user = new_user
            changed = True
    for old, new in ENGLISH_PROMPT_REWRITES:
        if old in user:
            user = user.replace(old, new)
            changed = True
    if re.match(r"^(Apply|Compute|Evaluate|Find|Calculate|Use|Solve|Determine)\b", user):
        user = (
            "Giải bài toán sau bằng tiếng Việt, trình bày từng bước và kết luận bằng LaTeX trong \\boxed{}:\n\n"
            + user
        )
        changed = True
    return user, changed


def record_score(rec: dict, formula: str) -> int:
    assistant = rec["messages"][2]["content"]
    score = len(assistant)
    if "**Tính toán" in assistant or "**Tính toán chi tiết" in assistant:
        score += 300
    if "**Bước 1:**" in assistant:
        score += 100
    if formula and len(formula) >= 8:
        score += min(len(formula), 200)
    if any(bad in assistant for bad in TEXT_REPLACEMENTS):
        score -= 500
    return score


def normalize_record(rec: dict) -> tuple[Optional[dict], Optional[str], list[str], bool]:
    reasons = []
    messages = rec.get("messages")
    if not isinstance(messages, list):
        return None, None, ["missing_messages"], False

    system = get_message(messages, "system") or DEFAULT_SYSTEM_PROMPT
    user = get_message(messages, "user")
    assistant = get_message(messages, "assistant")
    if not user:
        reasons.append("missing_user")
    if not assistant:
        reasons.append("missing_assistant")
    if reasons:
        return None, None, reasons, False

    user, prompt_changed = rewrite_user_prompt(user)
    assistant = clean_text(assistant)
    formula = extract_last_boxed_balanced(assistant)
    if not formula:
        reasons.append("missing_boxed_formula")
    elif not balanced_latex_braces(formula):
        reasons.append("bad_formula_braces")
    if not balanced_latex_braces(assistant):
        reasons.append("bad_assistant_braces")
    if not balanced_dollars(assistant):
        reasons.append("bad_assistant_dollars")
    if reasons:
        return None, formula, reasons, prompt_changed

    out = {
        "messages": [
            {"role": "system", "content": clean_text(system)},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "type": rec.get("type") or rec.get("meta", {}).get("type") or "algebra",
        "difficulty": rec.get("difficulty") or rec.get("meta", {}).get("difficulty") or "medium",
    }
    return out, formula, [], prompt_changed


def main():
    parser = argparse.ArgumentParser(description="Prepare a clean Vietnamese Qwen math SFT JSONL dataset")
    parser.add_argument("--input", "-i", default="DATA/augmented_train_data.jsonl")
    parser.add_argument("--output", "-o", default="DATA/qwen_vi_solve_train.jsonl")
    parser.add_argument("--keep-duplicates", action="store_true")
    args = parser.parse_args()

    total = 0
    kept = 0
    rewritten_prompts = 0
    invalid_records = 0
    invalid_reasons = Counter()
    type_counts = Counter()
    diff_counts = Counter()
    by_key: dict[tuple[str, str], tuple[int, dict]] = {}

    with open(args.input, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            total += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                invalid_reasons["bad_json"] += 1
                continue

            normalized, formula, reasons, prompt_changed = normalize_record(rec)
            if prompt_changed:
                rewritten_prompts += 1
            if reasons:
                invalid_records += 1
                invalid_reasons.update(reasons)
                continue

            key = (
                normalize_space(normalized["messages"][1]["content"]).lower(),
                normalize_formula(formula or ""),
            )
            score = record_score(normalized, formula or "")
            if args.keep_duplicates:
                key = (f"{line_no}:{key[0]}", key[1])
            prev = by_key.get(key)
            if prev is None or score > prev[0]:
                by_key[key] = (score, normalized)

    with open(args.output, "w", encoding="utf-8") as out:
        for _, rec in by_key.values():
            kept += 1
            type_counts[rec["type"]] += 1
            diff_counts[rec["difficulty"]] += 1
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Input records: {total:,}")
    print(f"Output records: {kept:,}")
    print(f"Duplicates removed: {total - kept - invalid_records:,}")
    print(f"Prompts rewritten for detailed Vietnamese solving: {rewritten_prompts:,}")
    print(f"Invalid skipped: {invalid_records:,} {dict(invalid_reasons)}")
    print(f"Types: {dict(type_counts.most_common())}")
    print(f"Difficulties: {dict(diff_counts.most_common())}")


if __name__ == "__main__":
    main()
