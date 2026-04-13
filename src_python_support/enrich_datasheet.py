from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DATA_PATH = Path("formulas/datasheet.json")


TYPE_HINTS = {
    "algebra": "bài toán đại số",
    "calculus": "bài toán giải tích",
    "geometry": "bài toán hình học",
    "trigonometry": "bài toán lượng giác",
    "linear_algebra": "bài toán đại số tuyến tính",
    "optimization": "bài toán tối ưu",
    "statistics": "bài toán thống kê",
    "sequences": "bài toán dãy số",
    "mathematical_physics": "bài toán hàm đặc biệt và vật lý toán",
    "combinatorics": "bài toán tổ hợp",
}


GLOBAL_TEXT_REPLACEMENTS = {
    r"\teat{": r"\text{",
    r"$x = \(\frac{y}{z}$\)": r"\(x = \frac{y}{z}\)",
    r"\(\lim_{x\) \to \(y^-}\) f(x) = \(z_1\)": r"\(\lim_{x \to y^-} f(x) = z_1\)",
    r"\(\lim_{x\) \to \(y^+}\) f(x) = \(z_2\)": r"\(\lim_{x \to y^+} f(x) = z_2\)",
    r"\(\lim_{x\) \to y} f(x)": r"\(\lim_{x \to y} f(x)\)",
    r"\({x_1\), \(x_2\), ..., \(x_n}\)": r"\(\{x_1, x_2, ..., x_n\}\)",
    r"\(f^-1\)": r"\(f^{-1}\)",
    r"\(f^-1(f(x)\))": r"\(f^{-1}(f(x))\)",
    r"\(P_n(x\))": r"\(P_n(x)\)",
    r"\(Q_n(x\))": r"\(Q_n(x)\)",
    r"\(P_r(x\))": r"\(P_r(x)\)",
    r"\(P_m(x\))": r"\(P_m(x)\)",
    r"\(J_n(x\))": r"\(J_n(x)\)",
    r"\(Y_n(x\))": r"\(Y_n(x)\)",
    r"\(J_{-n}(x\))": r"\(J_{-n}(x)\)",
    r"\(Y_{-n}(x\))": r"\(Y_{-n}(x)\)",
}


KNOWN_FIELD_FIXES = {
    "alg_fraction_standard_definition": {
        "reasoning": (
            "Sử dụng hệ biến chuẩn \\(x, y, z\\) và định dạng LaTeX "
            "\\(x = \\frac{y}{z}\\) để biểu diễn mối quan hệ tỉ lệ giữa các đại lượng. "
            "Việc dùng escape đúng định dạng giúp công thức được render ổn định khi truyền qua JSON."
        ),
    },
    "calc_limit_existence": {
        "steps": {
            1: "Tính giới hạn bên trái của hàm số khi x tiến tới y từ các giá trị nhỏ hơn: \\(\\lim_{x \\to y^-} f(x) = z_1\\)",
            2: "Tính giới hạn bên phải của hàm số khi x tiến tới y từ các giá trị lớn hơn: \\(\\lim_{x \\to y^+} f(x) = z_2\\)",
            4: "Kết luận: Giới hạn tồn tại nếu và chỉ nếu \\(z_1 = z_2 = z\\) (với z là số thực hữu hạn)",
        }
    },
    "calc_continuity_at_point": {
        "steps": {
            2: "Tính giới hạn của hàm số khi x tiến dần tới y: \\(\\lim_{x \\to y} f(x)\\)",
        }
    },
    "math_group_homomorphism_example_modulo": {
        "output": r"f(a) = a \pmod{5} \implies \text{Homomorphism}",
    },
}


BAD_SYMPY_SUBSTRINGS = (
    r"\text{False}",
    r"\text{True}",
    " de f i",
    " in mid",
    r"\frac{\phi}{G}",
    r"\frac{G}{H}",
    "Z mathbb",
)


BAD_OUTPUT_NORMALIZED_PATTERNS = (
    r"\text{False}",
    r"\text{True}",
    r"\teat{",
    " E mathbb",
    "mathbb E ",
)


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = " ".join(item.split()).strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def short_formula(text: str, limit: int = 110) -> str:
    value = " ".join(text.split())
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def apply_global_replacements(value: str) -> str:
    updated = value
    for old, new in GLOBAL_TEXT_REPLACEMENTS.items():
        updated = updated.replace(old, new)
    return updated


def walk_and_replace(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {key: walk_and_replace(val) for key, val in obj.items()}
    if isinstance(obj, list):
        return [walk_and_replace(val) for val in obj]
    if isinstance(obj, str):
        return apply_global_replacements(obj)
    return obj


def apply_known_field_fixes(item: dict[str, Any]) -> None:
    fixes = KNOWN_FIELD_FIXES.get(item.get("id"))
    if not fixes:
        return

    for field, value in fixes.items():
        if field == "steps" and isinstance(value, dict):
            steps = item.get("steps", [])
            for idx, step_value in value.items():
                if isinstance(steps, list) and 0 <= idx < len(steps):
                    steps[idx] = step_value
            continue
        item[field] = value


def extract_braced(text: str, start: int) -> tuple[str, int] | None:
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    chars: list[str] = []
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch == "{":
            depth += 1
            if depth == 1:
                continue
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return "".join(chars), idx
        if depth >= 1:
            chars.append(ch)
    return None


def swap_first_fraction(text: str) -> str | None:
    marker = r"\frac{"
    start = text.find(marker)
    if start == -1:
        return None
    numerator = extract_braced(text, start + len(r"\frac"))
    if numerator is None:
        return None
    denominator = extract_braced(text, numerator[1] + 1)
    if denominator is None:
        return None

    original = text[start : denominator[1] + 1]
    swapped = rf"\frac{{{denominator[0]}}}{{{numerator[0]}}}"
    if swapped == original:
        return None
    return text[:start] + swapped + text[denominator[1] + 1 :]


def square_first_denominator(text: str) -> str | None:
    marker = r"\frac{"
    start = text.find(marker)
    if start == -1:
        return None
    numerator = extract_braced(text, start + len(r"\frac"))
    if numerator is None:
        return None
    denominator = extract_braced(text, numerator[1] + 1)
    if denominator is None:
        return None

    original = text[start : denominator[1] + 1]
    updated = rf"\frac{{{numerator[0]}}}{{({denominator[0]})^2}}"
    if updated == original:
        return None
    return text[:start] + updated + text[denominator[1] + 1 :]


def flip_first_sign(text: str) -> str | None:
    if r"\pm" in text:
        return None
    for old, new in ((" + ", " - "), (" - ", " + ")):
        if old in text:
            return text.replace(old, new, 1)
    return None


def replace_once(text: str, old: str, new: str) -> str | None:
    if old not in text:
        return None
    return text.replace(old, new, 1)


def normalize_negative(value: str) -> str:
    updated = apply_global_replacements(value).strip()
    if r"\teat{" in updated:
        updated = updated.replace(r"\teat{", r"\text{")

    is_math_like = any(token in updated for token in ("\\", "=", "^", "_", "{", "}", "+", "-", r"\frac"))
    if not is_math_like and not updated.startswith(r"\text{"):
        updated = rf"\text{{{updated}}}"
    return updated


def build_instruction_variants(item: dict[str, Any]) -> list[str]:
    instruction = item.get("instruction", "").strip()
    existing = list(item.get("instruction_variants") or [])
    input_formula = short_formula(item.get("input", ""))
    type_hint = TYPE_HINTS.get(item.get("type"), "bài toán toán học")

    additions = [
        instruction,
        f"Hãy {lower_first(instruction)} và trả về kết quả bằng LaTeX chuẩn.",
        f"Giải {type_hint} này và chỉ xuất công thức cuối cùng đúng.",
        f"Viết đáp án ngắn gọn dưới dạng LaTeX chuẩn cho yêu cầu: {instruction}.",
        f"Chuẩn hóa kết quả về đúng cú pháp LaTeX cho bài toán: {instruction}.",
        f"Return only the final valid LaTeX for this {item.get('type', 'math')} formula task.",
    ]

    if input_formula:
        additions.append(f"Cho biểu thức {input_formula}, hãy suy ra kết quả đúng và xuất bằng LaTeX.")

    variants = dedupe_keep_order(existing + additions)
    return variants[:6]


def type_negative_candidates(item: dict[str, Any]) -> list[str]:
    item_type = item.get("type")
    tags = {str(tag) for tag in item.get("tags", [])}
    formula = item.get("canonical_form") or item.get("output") or item.get("input") or ""

    candidates: list[str] = []

    if r"\log" in formula or "logarithm" in tags:
        candidates.extend(
            [
                r"\log_z(xy) = \log_z x - \log_z y \text{ (sai dấu trong quy tắc log tích)}",
                r"\log_z(x^y) = (\log_z x)^y \text{ (sai: phải đưa hệ số y ra trước)}",
            ]
        )

    if r"\frac" in formula or "fraction" in tags:
        candidates.extend(
            [
                r"\frac{a}{b} + \frac{c}{d} = \frac{a+c}{bd} \text{ (sai: cộng phân số không cùng mẫu)}",
                r"\frac{a}{b} \cdot \frac{c}{d} = \frac{a+c}{b+d} \text{ (sai: nhầm nhân thành cộng)}",
            ]
        )

    if item_type == "trigonometry":
        candidates.extend(
            [
                r"\sin^2\theta + \cos^2\theta = 0 \text{ (sai: đẳng thức đúng phải bằng 1)}",
                r"\sin(\alpha+\beta) = \sin\alpha + \sin\beta \text{ (sai công thức cộng)}",
                r"\tan(2x) = 2\tan x \text{ (sai: thiếu mẫu số)}",
            ]
        )

    if item_type == "calculus" and r"\lim" in formula:
        candidates.extend(
            [
                r"\lim_{x \to y^-} f(x) \neq \lim_{x \to y^+} f(x) \text{ (trường hợp giới hạn không tồn tại)}",
                r"\lim_{x \to y} f(x) = \infty \text{ (không phải giới hạn hữu hạn trong ngữ cảnh này)}",
            ]
        )

    if item_type == "calculus" and r"\int" in formula:
        candidates.extend(
            [
                r"\int f(x)\,dx = F(x) \text{ (sai: thiếu hằng số } C\text{)}",
                r"\int e^{ax}\,dx = e^{ax} \text{ (sai: quên hệ số } 1/a\text{)}",
            ]
        )

    if item_type == "geometry":
        candidates.extend(
            [
                r"A = 2\pi r \text{ (sai: nhầm diện tích với chu vi)}",
                r"V = \pi r^2 \text{ (sai: nhầm thể tích với diện tích)}",
            ]
        )

    if item_type == "statistics":
        candidates.extend(
            [
                r"\mathrm{Var}(X) = \mathbb{E}[X] \text{ (sai: phương sai không đồng nhất với kỳ vọng)}",
                r"\mathrm{Cov}(X,Y) = \mathbb{E}[X]\mathbb{E}[Y] \text{ (sai: thiếu phần trừ và kỳ vọng tích)}",
            ]
        )

    if item_type == "linear_algebra":
        candidates.extend(
            [
                r"AB = BA \text{ (sai nói chung: nhân ma trận không giao hoán)}",
                r"\nabla(x^T A x) = Ax \text{ (sai: thiếu hạng } A^T x\text{ nếu } A \text{ không đối xứng)}",
            ]
        )

    if item_type == "optimization":
        candidates.extend(
            [
                r"\nabla f(x) = 0 \text{ luôn là cực tiểu} \text{ (sai: có thể là cực đại hoặc điểm yên ngựa)}",
                r"\theta_{t+1} = \theta_t + \eta \nabla f(\theta_t) \text{ (sai dấu cập nhật trong gradient descent)}",
            ]
        )

    if item_type == "sequences":
        candidates.extend(
            [
                r"S_n = \frac{n}{2}(a_1 + a_n) \text{ (sai: đây là công thức của cấp số cộng)}",
                r"a_n = a_1 + (n-1)r \text{ (sai: nhầm cấp số nhân với cấp số cộng)}",
            ]
        )

    if any(token in formula for token in (r"\phi", r"\mathbb{Z}", r"\trianglelefteq", r"\cong")):
        candidates.extend(
            [
                r"\phi(a*b) = \phi(a)*b \text{ (sai: không bảo toàn phép toán theo định nghĩa đồng cấu)}",
                r"G/H = G \cup H \text{ (sai: nhóm thương không phải hợp của hai tập)}",
            ]
        )

    if not candidates:
        candidates.extend(
            [
                r"x + y = xy \text{ (ví dụ sai: nhầm phép toán)}",
                r"x^m \cdot x^n = x^{mn} \text{ (ví dụ sai: nhầm quy tắc số mũ)}",
            ]
        )

    return candidates


def derived_negative_candidates(item: dict[str, Any]) -> list[str]:
    formula = item.get("canonical_form") or item.get("output") or item.get("input") or ""
    candidates: list[str] = []

    swapped = swap_first_fraction(formula)
    if swapped:
        candidates.append(rf"{swapped} \text{{ (sai: đảo tử và mẫu của phân số)}}")

    squared_den = square_first_denominator(formula)
    if squared_den:
        candidates.append(rf"{squared_den} \text{{ (sai: tự ý thay đổi mẫu số)}}")

    flipped = flip_first_sign(formula)
    if flipped:
        candidates.append(rf"{flipped} \text{{ (sai: đổi dấu không đúng)}}")

    trig_swaps = [
        (r"\sin", r"\cos", "sai: nhầm hàm sin thành cos"),
        (r"\cos", r"\sin", "sai: nhầm hàm cos thành sin"),
        (r"\tan", r"\sin", "sai: nhầm tan với sin"),
    ]
    for old, new, note in trig_swaps:
        replaced = replace_once(formula, old, new)
        if replaced:
            candidates.append(rf"{replaced} \text{{ ({note})}}")
            break

    return candidates


def build_negative_examples(item: dict[str, Any]) -> list[str]:
    existing = [normalize_negative(value) for value in (item.get("negative_examples") or []) if isinstance(value, str)]
    candidates = [normalize_negative(value) for value in derived_negative_candidates(item)]
    candidates.extend(normalize_negative(value) for value in type_negative_candidates(item))

    negatives = dedupe_keep_order(existing + candidates)
    return negatives[:4]


def should_reset_sympy(item: dict[str, Any]) -> bool:
    value = item.get("sympy_canonical_form")
    canonical = item.get("canonical_form")
    if not isinstance(value, str) or not canonical:
        return False

    if value.strip() in {"y = y", "z = z"}:
        return True

    if any(part in value for part in BAD_SYMPY_SUBSTRINGS):
        return True

    if re.search(r"(?<!\\)mathbb", value):
        return True

    if canonical.startswith(r"\phi") or r"\mathbb" in canonical:
        return True

    return False


def should_reset_output_normalized(item: dict[str, Any]) -> bool:
    value = item.get("output_normalized")
    if not isinstance(value, str):
        return False

    if any(part in value for part in BAD_OUTPUT_NORMALIZED_PATTERNS):
        return True

    if re.search(r"(?<!\\)mathbb", value):
        return True

    return False


def enrich() -> dict[str, int]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    stats = {
        "records": 0,
        "sympy_reset": 0,
        "output_normalized_reset": 0,
    }

    updated_data = walk_and_replace(data)

    for item in updated_data:
        stats["records"] += 1

        apply_known_field_fixes(item)

        item["instruction_variants"] = build_instruction_variants(item)
        item["negative_examples"] = build_negative_examples(item)

        if should_reset_sympy(item):
            item["sympy_canonical_form"] = item.get("canonical_form")
            stats["sympy_reset"] += 1

        if should_reset_output_normalized(item):
            item["output_normalized"] = item.get("output")
            stats["output_normalized_reset"] += 1

    DATA_PATH.write_text(
        json.dumps(updated_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return stats


def main() -> None:
    stats = enrich()
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
