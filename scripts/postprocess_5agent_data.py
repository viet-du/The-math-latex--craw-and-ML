"""
Post-process DATA/5agent_expanded/ and DATA/5agent_final/ in place.

This script applies the surgical fixes that were added to the upstream
data-generation scripts (Fix A: diversified agent3 fallback; Fix G:
Vietnamese placeholder substitution inside LaTeX). Running the upstream
scripts end-to-end requires the original raw inputs which may no
longer be available, so we walk the already-generated jsonl files and
rewrite the assistant content in place.

What it does:
  - For every jsonl under both folders (15 files each), read each row
    and apply `substitute_vietnamese_in_latex` to every assistant
    message -- this is Fix G (placeholder cleanup).
  - For agent3 specifically: detect the static boilerplate that was
    produced by the OLD `transform_for_agent3()` (one fixed 4-line
    Vietnamese paragraph used when `solution_steps` was empty) and
    replace those rows with a diversified template drawn from the
    shared `_AGENT3_FALLBACK_POOL`. The math_type is derived from the
    row's `id` (via its numeric suffix or by hashing the source
    template id); missing math_type falls back to `default`. This is
    Fix A (template rotation, kills the 64.87% mode-collapse on
    agent3 in 5agent_final/).

  - System and user messages are NEVER rewritten (their Vietnamese is
    meaningful narrative text, not placeholders).
  - Files are rewritten in place with the same encoding and JSON
    formatting style as the upstream scripts.

Usage:
    python scripts/postprocess_5agent_data.py
"""

import hashlib
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Re-use the canonical Fix A helpers (single source of truth).
from latex_vi_fixes import (
    _diversified_agent3_fallback_lines,
    substitute_vietnamese_in_latex,
)


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

# Old static boilerplate produced by an EARLIER version of
# `transform_for_agent3()` (or by `convert_datasheet_to_agents.py` before
# the prefix-doubling cleanup). The signature is "Bước 1: Bước 1: ..."
# (the prefix "Bước N:" is duplicated because the caller and the
# fallback template both add it). Any agent3 row whose content starts
# with this doubled prefix is mode-collapsed and must be replaced.
_OLD_BOILERPLATE_MARKERS = (
    "Bước 1: Bước 1: Xác định đúng bản chất",
    "Bước 1: Bước 1: Nhận diện đúng",
    "Bước 1: Bước 1: Đọc và hiểu bài toán",
    "Bước 1: Bước 1: Xác định dạng",
    "Bước 1: Bước 1: Phân tích",
    # Older 4-line Vietnamese paragraph used by the very first version of
    # the script (kept for safety in case some files still carry it).
    "Đọc và hiểu bài toán",
    "Xác định các đại lượng và công thức cần dùng",
    "Thực hiện tính toán theo các bước logic",
)


def _is_old_boilerplate(text: str) -> bool:
    """True iff `text` looks like a static agent3 boilerplate that the
    previous data-generation scripts emitted for every empty-steps row.
    Detection rules (any one is enough):
      - starts with the doubled prefix "Bước 1: Bước 1: " and matches
        one of the known markers (default / trigonometry / algebra
        / logarithm / geometry pool entries);
      - contains all three lines of the very first 3-line fallback.
    """
    if text.startswith("Bước 1: Bước 1: "):
        body = text[len("Bước 1: Bước 1: "):]
        for marker in _OLD_BOILERPLATE_MARKERS:
            if marker.startswith("Bước 1: Bước 1:") and marker[len("Bước 1: Bước 1: "):] in body:
                return True
    # Fall-back: 3-line Vietnamese paragraph used by the very first script.
    return all(marker in text for marker in _OLD_BOILERPLATE_MARKERS[5:])


# Reasonable math_type values keyed off common Vietnamese / English
# category labels seen in the dataset. If we cannot infer anything we
# fall back to "default".
_CATEGORY_TO_MATH_TYPE = {
    "algebra": "algebra",
    "đại số": "algebra",
    "dai so": "algebra",
    "geometry": "geometry",
    "hình học": "geometry",
    "hinh hoc": "geometry",
    "calculus": "calculus",
    "giải tích": "calculus",
    "giai tich": "calculus",
    "fraction": "algebra",
    "phân số": "algebra",
    "phan so": "algebra",
    "percentage": "algebra",
    "phần trăm": "algebra",
    "phan tram": "algebra",
    "ratio": "algebra",
    "tỉ lệ": "algebra",
    "ti le": "algebra",
    "motion": "algebra",
    "chuyển động": "algebra",
    "chuyen dong": "algebra",
    "probability": "probability",
    "xác suất": "probability",
    "xac suat": "probability",
    "statistics": "probability",
    "thống kê": "probability",
    "thong ke": "probability",
    "machine_learning": "linear_algebra",
    "học máy": "linear_algebra",
    "hoc may": "linear_algebra",
    "deep_learning": "linear_algebra",
    "học sâu": "linear_algebra",
    "hoc sau": "linear_algebra",
    "linear_algebra": "linear_algebra",
    "đại số tuyến tính": "linear_algebra",
    "dai so tuyen tinh": "linear_algebra",
    "trigonometry": "trigonometry",
    "lượng giác": "trigonometry",
    "luong giac": "trigonometry",
}


def _infer_math_type_from_row(row: dict, fallback: str = "default") -> str:
    """Best-effort math_type extraction from a row. Order of attempts:
    1. row['math_type'] (used by some datasets)
    2. row['category'] (used by transform_for_5agent.py)
    3. row['type'] (used by convert_datasheet_to_agents.py)
    4. row['messages'] user content (very loose keyword scan)
    5. fallback
    """
    for key in ("math_type", "category", "type"):
        val = row.get(key)
        if isinstance(val, str) and val:
            mt = _CATEGORY_TO_MATH_TYPE.get(val.strip().lower())
            if mt:
                return mt
    # 4: scan the user message for keywords (very loose).
    try:
        user_text = " ".join(
            m.get("content", "") for m in row.get("messages", []) if m.get("role") == "user"
        ).lower()
    except Exception:
        user_text = ""
    for key, mt in _CATEGORY_TO_MATH_TYPE.items():
        if key in user_text:
            return mt
    return fallback


def _stable_example_idx(row_id: str) -> int:
    """Return a deterministic non-negative integer derived from the row's
    `id` field. Used to seed the template-rotation so the same row
    always picks the same template across regenerations.
    """
    if not row_id:
        return 0
    digest = hashlib.md5(row_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _build_full_reasoning_block(math_type: str, example_idx: int) -> str:
    """Return a multi-line reasoning block for an agent3 row whose
    current content is mode-collapsed. We use the same pool as the
    upstream `_diversified_agent3_fallback_lines` but compose a
    4-line block by walking 4 consecutive entries from the chosen pool
    (offset by the same `example_idx`). This keeps the resulting
    assistant content length comparable to the original 4-step fallback
    and ensures the per-row string varies across thousands of rows
    even though each pool only has a handful of entries.
    """
    key = (math_type or "default").lower().replace(" ", "_")
    pool = (
        _AGENT3_FALLBACK_POOL.get(key)
        or _AGENT3_FALLBACK_POOL.get("default")
        or []
    )
    if not pool:
        return ""
    n = len(pool)
    start = abs(example_idx) % n
    lines = []
    for offset in range(4):
        entry = pool[(start + offset) % n]
        if "\n" in entry:
            lines.extend(entry.split("\n"))
        else:
            lines.append(entry)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-file rewrite
# ---------------------------------------------------------------------------


def _rewrite_assistant_with_fixes(row: dict, agent_id: str) -> bool:
    """Apply Fix A (agent3 template rotation, only when the row carries
    the OLD boilerplate) and Fix G (placeholder substitution in every
    assistant message's LaTeX blocks). Returns True iff the row was
    mutated.
    """
    mutated = False
    msgs = row.get("messages") or []

    # ---- Fix A: rotate the static boilerplate in agent3 rows. ----
    if agent_id == "agent3":
        last_idx = len(msgs) - 1
        if last_idx >= 0 and msgs[last_idx].get("role") == "assistant":
            old_text = msgs[last_idx].get("content", "")
            if _is_old_boilerplate(old_text):
                row_id = row.get("id", "") or ""
                example_idx = _stable_example_idx(row_id)
                math_type = _infer_math_type_from_row(row)
                # `_diversified_agent3_fallback_lines` returns 1 pool
                # entry (1 line). For an in-place postprocess pass we
                # need a multi-line block, so we walk 4 consecutive
                # entries from the same pool. This keeps the dataset
                # length comparable to the original 4-step fallback and
                # gives us many more unique strings (4^N where N =
                # rows / pool size).
                new_text = _build_full_reasoning_block(math_type, example_idx)
                if new_text:
                    msgs[last_idx]["content"] = new_text
                    mutated = True

    # ---- Fix G: clean up Vietnamese placeholders inside LaTeX. ----
    for msg in msgs:
        if msg.get("role") != "assistant":
            continue
        old_content = msg.get("content", "")
        new_content = substitute_vietnamese_in_latex(old_content)
        if new_content != old_content:
            msg["content"] = new_content
            mutated = True

    return mutated


def _process_folder(folder: str) -> dict:
    """Walk every jsonl under `folder` and rewrite rows in place.

    Returns a small stats dict for logging.
    """
    stats = {
        "folder": folder,
        "files": 0,
        "rows": 0,
        "fix_a_rows": 0,
        "fix_g_rows": 0,
    }
    if not os.path.isdir(folder):
        print(f"  [skip] {folder} does not exist")
        return stats

    for split in ("train", "val", "test"):
        split_dir = os.path.join(folder, split)
        if not os.path.isdir(split_dir):
            continue
        for agent_id in (f"agent{i}" for i in range(1, 6)):
            path = os.path.join(split_dir, f"{agent_id}.jsonl")
            if not os.path.exists(path):
                continue
            new_rows = []
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        new_rows.append(line)
                        continue
                    was_old_boilerplate = False
                    if agent_id == "agent3":
                        try:
                            asst_text = rec["messages"][-1]["content"]
                            was_old_boilerplate = _is_old_boilerplate(asst_text)
                        except Exception:
                            was_old_boilerplate = False
                    mutated = _rewrite_assistant_with_fixes(rec, agent_id)
                    if mutated:
                        if was_old_boilerplate:
                            stats["fix_a_rows"] += 1
                        else:
                            stats["fix_g_rows"] += 1
                    new_rows.append(rec)
                    stats["rows"] += 1
            with open(path, "w", encoding="utf-8") as fh:
                for rec in new_rows:
                    if isinstance(rec, str):
                        fh.write(rec + "\n")
                    else:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            stats["files"] += 1
    return stats


def main():
    print("=" * 70)
    print("POST-PROCESS 5-AGENT DATA (Fix A + Fix G, in place)")
    print("=" * 70)
    for folder in ("DATA/5agent_expanded", "DATA/5agent_final"):
        print(f"\n--- {folder} ---")
        stats = _process_folder(folder)
        print(
            f"   files={stats['files']}  rows={stats['rows']}  "
            f"fix_a_rows={stats['fix_a_rows']}  "
            f"fix_g_rows={stats['fix_g_rows']}"
        )
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()