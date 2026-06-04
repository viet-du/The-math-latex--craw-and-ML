#!/usr/bin/env python3
import json
import argparse
import re
from collections import Counter


def balanced_braces(s: str) -> bool:
    stack = []
    pairs = {'}':'{', ']':'[', ')':'('}
    for ch in s:
        if ch in '{[(':
            stack.append(ch)
        elif ch in '}])':
            if not stack or stack[-1] != pairs[ch]:
                return False
            stack.pop()
    return not stack


def balanced_latex_braces(s: str) -> bool:
    depth = 0
    for ch in s:
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def balanced_dollars(s: str) -> bool:
    # count of single $ should be even; ignore escaped \$
    count = 0
    i = 0
    while i < len(s):
        if s[i] == '$':
            # check escape
            if i > 0 and s[i-1] == '\\':
                i += 1
                continue
            count += 1
        i += 1
    return count % 2 == 0


def is_likely_latex(s: str) -> bool:
    if not s:
        return False
    latex_tokens = ['\\', '\\frac', '\\int', '\\sum', '^', '_', '\\sqrt', '\\tan', '\\sin', '\\cos']
    return any(tok in s for tok in latex_tokens)


def normalize_formula(s: str) -> str:
    if s is None:
        return ''
    # simple normalization: strip, collapse spaces
    s2 = ' '.join(s.split())
    return s2


def validate_formula(s: str) -> tuple[bool, list[str]]:
    reasons = []
    norm = normalize_formula(s)
    if not norm:
        reasons.append('empty')
    if norm and not balanced_latex_braces(norm):
        reasons.append('unbalanced_latex_braces')
    if norm and not balanced_dollars(norm):
        reasons.append('unbalanced_dollars')
    return not reasons, reasons


def main():
    p = argparse.ArgumentParser(description='Validate and dedupe normalized JSONL records')
    p.add_argument('--input', '-i', default='DATA/augmented_train_data_cleaned.jsonl')
    p.add_argument('--output', '-o', default='DATA/augmented_train_data_validated.jsonl')
    p.add_argument('--drop-invalid', action='store_true', help='skip records with invalid final_formula')
    args = p.parse_args()

    seen = set()
    total = 0
    invalid = 0
    duplicates = 0
    kept = 0
    reason_counts = Counter()
    sample_invalid = []
    sample_dupes = []

    with open(args.input, 'r', encoding='utf-8') as inf, open(args.output, 'w', encoding='utf-8') as outf:
        for line in inf:
            total += 1
            rec = json.loads(line)
            formula = rec.get('final_formula') or ''
            norm = normalize_formula(formula)
            ok, reasons = validate_formula(formula)
            if not ok:
                invalid += 1
                reason_counts.update(reasons)
                if len(sample_invalid) < 10:
                    sample_invalid.append({
                        'line': total,
                        'reasons': reasons,
                        'input': rec.get('input'),
                        'final_formula': formula,
                    })
                if args.drop_invalid:
                    continue
                rec['flag'] = (rec.get('flag','') + '|invalid_formula').strip('|')
            key = ( (rec.get('input') or '').strip(), norm )
            if key in seen:
                duplicates += 1
                if len(sample_dupes) < 10:
                    sample_dupes.append({'line': total, 'input': rec.get('input'), 'final_formula': formula})
                continue
            seen.add(key)
            kept += 1
            outf.write(json.dumps(rec, ensure_ascii=False) + '\n')

    print(f'Total input records: {total}')
    print(f'Kept (unique): {kept}')
    print(f'Duplicates skipped: {duplicates}')
    print(f'Invalid formula count: {invalid}')
    if reason_counts:
        print(f'Invalid reasons: {dict(reason_counts)}')
    if sample_invalid:
        print('\nSample invalid formulas:')
        for s in sample_invalid:
            print(json.dumps(s, ensure_ascii=False))
    if sample_dupes:
        print('\nSample duplicates:')
        for s in sample_dupes:
            print(json.dumps(s, ensure_ascii=False))


if __name__ == '__main__':
    main()
