#!/usr/bin/env python3
"""Map samples in a JSONL file to entries in datasheet.json using fuzzy matching.
Writes a mapped JSONL and a JSONL report with match scores.
"""
import json
import argparse
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = str(s)
    s = unicodedata.normalize('NFKD', s)
    s = s.lower()
    # Remove LaTeX commands and math delimiters
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\{[^}]*\})?", " ", s)
    s = s.replace('\\', ' ')
    s = s.replace('$', ' ')
    # Keep alphanumeric and spaces
    s = re.sub(r'[^0-9a-z]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def extract_user_text(sample: dict) -> str:
    # Qwen chat format: messages array
    if isinstance(sample.get('messages'), list):
        parts = []
        for m in sample['messages']:
            if m.get('role') == 'user' and m.get('content'):
                parts.append(m.get('content'))
        if parts:
            return ' '.join(parts)
    # fallback to common fields
    for k in ('input', 'instruction', 'content', 'prompt', 'query'):
        v = sample.get(k)
        if v:
            return v
    # try top-level 'user' or 'question'
    for k in ('user', 'question'):
        v = sample.get(k)
        if v:
            return v
    return ''


def candidate_text_from_datasheet_item(item: dict) -> str:
    parts = []
    for k in ('instruction', 'canonical_form', 'output', 'input', 'sympy_canonical_form'):
        v = item.get(k)
        if isinstance(v, str):
            parts.append(v)
    # variants
    for k in ('instruction_variants', 'input_variants'):
        arr = item.get(k)
        if isinstance(arr, list):
            for v in arr:
                if isinstance(v, str):
                    parts.append(v)
    # example problems
    ex = item.get('example_problems')
    if isinstance(ex, list):
        for e in ex:
            if isinstance(e, dict):
                for vv in e.values():
                    if isinstance(vv, str):
                        parts.append(vv)
    return ' '.join(parts)


def score(a: str, b: str):
    if not a or not b:
        return 0.0
    a_n = normalize_text(a)
    b_n = normalize_text(b)
    if not a_n or not b_n:
        return 0.0
    # Sequence matcher ratio
    ratio = SequenceMatcher(None, a_n, b_n).ratio()
    # token overlap
    ta = set(a_n.split())
    tb = set(b_n.split())
    if not ta or not tb:
        token_overlap = 0.0
    else:
        token_overlap = len(ta & tb) / len(ta | tb)
    # combine scores conservatively
    return max(ratio, token_overlap)


def load_datasheet(path: Path):
    with path.open('r', encoding='utf-8') as f:
        data = json.load(f)
    # ensure list
    if isinstance(data, dict):
        # maybe top-level contains 'items'
        data = data.get('items', [])
    return data


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--datasheet', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--report', required=True)
    p.add_argument('--threshold', type=float, default=0.8)
    p.add_argument('--topk', type=int, default=1)
    args = p.parse_args()

    input_path = Path(args.input)
    ds_path = Path(args.datasheet)
    out_path = Path(args.output)
    report_path = Path(args.report)

    datasheet = load_datasheet(ds_path)
    candidates = []
    for item in datasheet:
        txt = candidate_text_from_datasheet_item(item)
        candidates.append((item.get('id'), txt, item))

    total = 0
    matched = 0
    unmatched = 0

    with input_path.open('r', encoding='utf-8') as fin, \
         out_path.open('w', encoding='utf-8') as fout, \
         report_path.open('w', encoding='utf-8') as frep:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            total += 1
            j = json.loads(line)
            user_text = extract_user_text(j)
            best_score = 0.0
            best_item = None
            best_id = None
            # iterate candidates
            for cid, ctext, item in candidates:
                s = score(user_text, ctext)
                if s > best_score:
                    best_score = s
                    best_item = item
                    best_id = cid

            mapped = False
            if best_score >= args.threshold and best_item is not None:
                mapped = True
                # ensure metadata exists
                meta = j.get('metadata')
                if meta is None or not isinstance(meta, dict):
                    j['metadata'] = {}
                    meta = j['metadata']
                # copy id/type/difficulty if present
                if best_item.get('id'):
                    meta['id'] = best_item.get('id')
                if best_item.get('type'):
                    meta['type'] = best_item.get('type')
                if best_item.get('difficulty'):
                    meta['difficulty'] = best_item.get('difficulty')
                # annotate mapping info
                meta['mapped_from_datasheet'] = best_item.get('id')
                meta['mapping_score'] = round(best_score, 4)
                matched += 1
            else:
                unmatched += 1

            fout.write(json.dumps(j, ensure_ascii=False) + '\n')

            # write report line
            rep = {
                'orig_id': (j.get('metadata') or {}).get('id') or j.get('id'),
                'user_text_snippet': (user_text or '')[:300],
                'best_match_id': best_id,
                'best_score': round(best_score, 4),
                'mapped': bool(mapped)
            }
            frep.write(json.dumps(rep, ensure_ascii=False) + '\n')

    print(f"Total={total}, matched={matched}, unmatched={unmatched}")


if __name__ == '__main__':
    main()
