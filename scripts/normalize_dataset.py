#!/usr/bin/env python3
import argparse
import json
import re
from typing import Optional

BOXED_RE = re.compile(r"\\boxed\{([^}]*)\}")
BRACKET_RE = re.compile(r"\\\[(.*?)\\\]", re.S)
DOLLAR_RE = re.compile(r"(?<!\\)\$(.+?)(?<!\\)\$", re.S)


def extract_last_boxed_balanced(text: str) -> Optional[str]:
    """Find the last occurrence of "\\boxed{" and extract balanced braces content."""
    key = r"\boxed{"
    idx = text.rfind(key)
    if idx == -1:
        return None
    start = idx + len(key)
    depth = 1
    i = start
    buf = []
    while i < len(text):
        ch = text[i]
        if ch == '{':
            depth += 1
            buf.append(ch)
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return ''.join(buf).strip()
            buf.append(ch)
        else:
            buf.append(ch)
        i += 1
    return None


def extract_formula(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    # prefer last \boxed{...} with balanced-brace extraction
    boxed_bal = extract_last_boxed_balanced(text)
    if boxed_bal:
        return boxed_bal
    # fallback to regex (non-nested)
    boxed = BOXED_RE.findall(text)
    if boxed:
        return boxed[-1].strip()
    # then \[ ... \]
    br = BRACKET_RE.findall(text)
    if br:
        return br[-1].strip()
    # then $...$
    doll = DOLLAR_RE.findall(text)
    if doll:
        return doll[-1].strip()
    # fallback: try to heuristically find a math-like line from the end
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in reversed(lines):
        if any(ch in line for ch in ['\\', '^', '_', '{', '}', '=', '\\frac', '\\int', '\\sum', '\\sqrt', '$']):
            # remove surrounding $ if present
            line = line.strip()
            if line.startswith('$') and line.endswith('$') and len(line) > 1:
                return line[1:-1].strip()
            return line
    return None


def normalize_record(rec: dict) -> dict:
    # Extract messages if present
    msgs = rec.get('messages', [])
    system = rec.get('system')
    user = rec.get('user')
    assistant = rec.get('assistant')

    if msgs and not (system or user or assistant):
        # Extract by roles
        for m in msgs:
            role = m.get('role')
            content = m.get('content') or m.get('text') or m.get('message')
            if role == 'system' and not system:
                system = content
            elif role == 'user' and not user:
                user = content
            elif role == 'assistant' and not assistant:
                assistant = content
        # If multiple user/assistant messages, prefer the last occurrence
        for role in ('user','assistant'):
            found = [m.get('content') or m.get('text') or m.get('message') for m in msgs if m.get('role')==role]
            if found:
                if role == 'user':
                    user = found[-1]
                else:
                    assistant = found[-1]

    formula = extract_formula(assistant)

    meta = {k: v for k, v in rec.items() if k not in ('messages', 'system', 'user', 'assistant')}

    out = {
        'system': system,
        'input': user,
        'final_formula': formula,
        'meta': meta,
    }
    if formula is None:
        out['flag'] = 'no_formula'
    return out


def main():
    p = argparse.ArgumentParser(description='Normalize augmented JSONL dataset extracting final LaTeX formula')
    p.add_argument('--input', '-i', default='DATA/augmented_train_data.jsonl')
    p.add_argument('--output', '-o', default='DATA/augmented_train_data_cleaned.jsonl')
    p.add_argument('--sample', '-s', type=int, default=10, help='number of sample records to print')
    p.add_argument('--strict', action='store_true', help='skip records without an extracted formula')
    args = p.parse_args()

    total = 0
    with_formula = 0
    no_formula = 0
    samples = []

    with open(args.input, 'r', encoding='utf-8') as inf, open(args.output, 'w', encoding='utf-8') as outf:
        for line in inf:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                # try to fix common trailing commas by naive trimming
                try:
                    rec = json.loads(line.rstrip(',\n'))
                except Exception:
                    continue
            total += 1
            out = normalize_record(rec)
            if out.get('final_formula'):
                with_formula += 1
            else:
                no_formula += 1
                if args.strict:
                    continue
            if len(samples) < args.sample:
                samples.append(out)
            outf.write(json.dumps(out, ensure_ascii=False) + '\n')

    print(f'Total records: {total}')
    print(f'With formula: {with_formula}')
    print(f'No formula: {no_formula}')
    print('\nSample outputs:')
    for s in samples:
        print(json.dumps(s, ensure_ascii=False))


if __name__ == '__main__':
    main()
