"""
Diagnose 5-Agent Training Data
================================

Quantify two known problems across all 5 agents x 3 splits for both
DATA/5agent_expanded/ and DATA/5agent_final/ (whichever exist):

  1. Template-soup / mode-collapse:
       mode_collapse_pct = (top_string_count / total_rows) * 100
     where `top_string_count` is the largest single occurrence count
     of an exact-match assistant content string in the file. A high
     value means the LoRA target for that agent is dominated by one
     static template.

  2. Vietnamese placeholder leak in LaTeX:
       placeholder_pct = (rows_with_any_placeholder / total_rows) * 100
     where `rows_with_any_placeholder` counts rows whose LAST (assistant)
     message contains any of {một, hai, ba, bi, trái, phải} inside
     a `$...$` / `$$...$$` LaTeX block. These placeholders were meant
     to be substituted with LaTeX math symbols but were not.

The script prints a fixed-width table to stdout and writes a structured
JSON report to DATA/diagnostic_report.json.

Usage:
    python scripts/diagnose_5agent_data.py
"""

import json
import os
import re
import sys
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# Same regex / placeholder set as Fix G in scripts/convert_datasheet_to_agents.py.
_LATEX_BLOCK_RE = re.compile(r"(\$\$?)([^$]+?)\1")
_PLACEHOLDERS = ("một", "hai", "ba", "bi", "trái", "phải")

_FOLDERS = ("DATA/5agent_expanded", "DATA/5agent_final")
_SPLITS = ("train", "val", "test")
_AGENTS = tuple(f"agent{i}" for i in range(1, 6))


def _has_placeholder_in_latex(text: str) -> bool:
    """True iff any placeholder appears inside a `$...$` / `$$...$$`
    LaTeX block. Vietnamese text outside LaTeX is ignored."""
    for m in _LATEX_BLOCK_RE.finditer(text):
        body = m.group(2)
        for ph in _PLACEHOLDERS:
            if ph in body:
                return True
    return False


def _diagnose_file(jsonl_path: str):
    """Return dict of metrics for one agent jsonl file."""
    total = 0
    placeholder_rows = 0
    assistant_counter: Counter = Counter()
    if not os.path.exists(jsonl_path):
        return None
    with open(jsonl_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                asst = rec["messages"][-1]["content"]
            except Exception:
                continue
            total += 1
            assistant_counter[asst] += 1
            if _has_placeholder_in_latex(asst):
                placeholder_rows += 1
    top_count = max(assistant_counter.values()) if assistant_counter else 0
    unique = len(assistant_counter)
    return {
        "total_rows": total,
        "unique_assistant_strings": unique,
        "top_string_count": top_count,
        "mode_collapse_pct": round(top_count / total * 100, 2) if total else 0.0,
        "placeholder_rows": placeholder_rows,
        "placeholder_pct": round(placeholder_rows / total * 100, 2) if total else 0.0,
    }


def _print_table(report: dict):
    """Print a fixed-width table for both folders."""
    header_cols = ("split", "agent", "total", "unique", "mode_collapse_pct", "placeholder_pct")
    cols_widths = (6, 8, 7, 8, 18, 16)
    line_fmt = "  ".join(f"{{:<{w}}}" for w in cols_widths)

    print("=" * 78)
    print("5-AGENT DATA DIAGNOSTIC REPORT")
    print("=" * 78)
    for folder in _FOLDERS:
        if folder not in report:
            print(f"\n[skip] {folder} not present")
            continue
        print(f"\n--- {folder} ---")
        print(line_fmt.format(*header_cols))
        print("-" * 78)
        for split in _SPLITS:
            if split not in report[folder]:
                continue
            for agent in _AGENTS:
                m = report[folder][split].get(agent)
                if m is None:
                    continue
                print(
                    line_fmt.format(
                        split,
                        agent,
                        m["total_rows"],
                        m["unique_assistant_strings"],
                        f"{m['mode_collapse_pct']:.2f}%",
                        f"{m['placeholder_pct']:.2f}%",
                    )
                )

    # Worst-offender summary: rows with mode_collapse > 50% or
    # placeholder_pct > 10%. These are the rows that motivated the
    # Fix A (template diversification) and Fix G (placeholder
    # substitution) patches.
    print("\n" + "=" * 78)
    print("WORST OFFENDERS  (mode_collapse > 50% OR placeholder_pct > 10%)")
    print("=" * 78)
    found_any = False
    for folder in _FOLDERS:
        if folder not in report:
            continue
        for split in _SPLITS:
            for agent in _AGENTS:
                m = report[folder][split].get(agent)
                if m is None:
                    continue
                if m["mode_collapse_pct"] > 50 or m["placeholder_pct"] > 10:
                    found_any = True
                    print(
                        f"  {folder}/{split}/{agent}  "
                        f"mode_collapse={m['mode_collapse_pct']:.2f}%  "
                        f"placeholder={m['placeholder_pct']:.2f}%"
                    )
    if not found_any:
        print("  (none — both metrics within thresholds)")


def main():
    report = {}
    for folder in _FOLDERS:
        if not os.path.isdir(folder):
            continue
        report[folder] = {}
        for split in _SPLITS:
            split_dir = os.path.join(folder, split)
            if not os.path.isdir(split_dir):
                continue
            report[folder][split] = {}
            for agent in _AGENTS:
                path = os.path.join(split_dir, f"{agent}.jsonl")
                metrics = _diagnose_file(path)
                if metrics is not None:
                    report[folder][split][agent] = metrics

    _print_table(report)

    out_path = "DATA/diagnostic_report.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"\nJSON report written to: {out_path}")


if __name__ == "__main__":
    main()
