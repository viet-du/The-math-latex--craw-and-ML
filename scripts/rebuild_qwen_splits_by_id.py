#!/usr/bin/env python3
"""
Merge Qwen-format JSONL files, deduplicate by user prompt, map entries without IDs to existing IDs when possible,
then split by ID (all samples with same ID go to same split) to produce train/val JSONL with no ID leakage.

Usage:
  python scripts/rebuild_qwen_splits_by_id.py \
    --inputs DATA/qwen_train.jsonl DATA/qwen_vi_solve_train.jsonl DATA/qwen_val.jsonl \
    --datasheet DATA/datasheet.json \
    --train-out DATA/qwen_merged_train_byid.jsonl \
    --val-out DATA/qwen_resplit_val_byid.jsonl \
    --val-frac 0.05 --seed 42

The script will:
 - prefer existing metadata.id when present
 - match user messages exactly (normalized) to assign IDs
 - if a sample lacks ID and matches no existing user prompt, create a generated ID
 - move top-level `type`/`difficulty` fields into `metadata` if present
 - dedupe exact duplicate user prompts across inputs (keep first occurrence according to input order)
 - report statistics
"""

import argparse
import json
import random
import re
import unicodedata
from pathlib import Path
from typing import Dict, Any, List


def normalize_text(s: str) -> str:
    if s is None:
        return ''
    s = unicodedata.normalize('NFKC', s)
    s = s.replace('\r\n', '\n').replace('\t', ' ')
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n+', ' ', s)
    s = s.strip().lower()
    return s


def load_jsonl(path: Path):
    with path.open('r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                # try to be robust for truncated lines
                try:
                    # fallback: skip line
                    continue
                except Exception:
                    continue


def write_jsonl(path: Path, objects: List[Dict[str,Any]]):
    with path.open('w', encoding='utf-8') as f:
        for obj in objects:
            f.write(json.dumps(obj, ensure_ascii=False) + '\n')


def get_user_message(sample: Dict[str,Any]) -> str:
    # Qwen-format: messages is a list of {role, content}
    msgs = sample.get('messages') or []
    for m in msgs:
        if m.get('role') == 'user':
            return m.get('content','')
    # fallback: second message
    if len(msgs) >= 2:
        return msgs[1].get('content','')
    # fallback: try top-level fields 'instruction' or 'input'
    return (sample.get('instruction') or '') + '\n' + (sample.get('input') or '')


def build_datasheet_map(datasheet_path: Path):
    if not datasheet_path.exists():
        return {}, {}
    try:
        with datasheet_path.open('r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return {}, {}
    # map normalized instruction/input variants to id, and id->item
    variant_to_id = {}
    id_to_item = {}
    for item in data:
        item_id = item.get('id')
        id_to_item[item_id] = item
        # instruction and variants
        for key in ('instruction', 'instruction_variants', 'input', 'input_variants'):
            val = item.get(key)
            if not val:
                continue
            if isinstance(val, list):
                for x in val:
                    if not x:
                        continue
                    variant_to_id[normalize_text(x)] = item_id
            else:
                variant_to_id[normalize_text(val)] = item_id
    return variant_to_id, id_to_item


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', nargs='+', required=True)
    parser.add_argument('--datasheet', default='DATA/datasheet.json')
    parser.add_argument('--train-out', default='DATA/qwen_merged_train_byid.jsonl')
    parser.add_argument('--val-out', default='DATA/qwen_resplit_val_byid.jsonl')
    parser.add_argument('--val-frac', type=float, default=0.05)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--dedupe', action='store_true', default=True)
    args = parser.parse_args()

    input_paths = [Path(p) for p in args.inputs]
    datasheet_path = Path(args.datasheet)

    variant_to_id_map, id_to_item = build_datasheet_map(datasheet_path)

    user_to_id: Dict[str,str] = {}
    id_to_samples: Dict[str,List[Dict[str,Any]]] = {}
    seen_user_text: set = set()
    generated_counter = 0
    duplicates = 0
    mapped_from_train = 0
    mapped_from_datasheet = 0

    # process files in order
    for p in input_paths:
        if not p.exists():
            print(f'Warning: input {p} not found, skipping')
            continue
        for sample in load_jsonl(p):
            user_text = get_user_message(sample)
            norm_user = normalize_text(user_text)
            if args.dedupe and norm_user in seen_user_text:
                duplicates += 1
                continue
            # get id from metadata if present
            sample_id = None
            meta = sample.get('metadata') or {}
            if isinstance(meta, dict) and meta.get('id'):
                sample_id = meta.get('id')
            else:
                # if this user text was seen in earlier samples, reuse id
                if norm_user in user_to_id:
                    sample_id = user_to_id[norm_user]
                    mapped_from_train += 1
                elif norm_user in variant_to_id_map:
                    sample_id = variant_to_id_map[norm_user]
                    mapped_from_datasheet += 1
                else:
                    generated_counter += 1
                    sample_id = f'gen_{generated_counter}'

            # ensure metadata dict
            if not isinstance(meta, dict):
                meta = {}
            meta['id'] = sample_id
            # move top-level type/difficulty into metadata if present
            if 'type' in sample and 'type' not in meta:
                meta['type'] = sample.get('type')
            if 'difficulty' in sample and 'difficulty' not in meta:
                meta['difficulty'] = sample.get('difficulty')

            # fill missing type/difficulty from datasheet if available
            if sample_id in id_to_item:
                ds_item = id_to_item[sample_id]
                if 'type' not in meta and ds_item.get('type'):
                    meta['type'] = ds_item.get('type')
                if 'difficulty' not in meta and ds_item.get('difficulty'):
                    meta['difficulty'] = ds_item.get('difficulty')

            sample['metadata'] = meta

            # register
            seen_user_text.add(norm_user)
            user_to_id[norm_user] = sample_id
            id_to_samples.setdefault(sample_id, []).append(sample)

    all_ids = list(id_to_samples.keys())
    print(f'Unique IDs found: {len(all_ids)}')
    total_samples = sum(len(v) for v in id_to_samples.values())
    print(f'Total samples after dedupe: {total_samples} (duplicates skipped: {duplicates})')
    print(f'Mapped from existing user prompts: {mapped_from_train}, mapped by datasheet variants: {mapped_from_datasheet}, generated new ids: {generated_counter}')

    # split by ID
    random.seed(args.seed)
    ids_shuffled = list(all_ids)
    random.shuffle(ids_shuffled)
    val_count = max(1, int(len(ids_shuffled) * args.val_frac))
    val_ids = set(ids_shuffled[:val_count])
    train_ids = set(ids_shuffled[val_count:])

    train_samples = []
    val_samples = []
    for _id in train_ids:
        train_samples.extend(id_to_samples.get(_id, []))
    for _id in val_ids:
        val_samples.extend(id_to_samples.get(_id, []))

    # write outputs
    write_jsonl(Path(args.train_out), train_samples)
    write_jsonl(Path(args.val_out), val_samples)

    print(f'Wrote {len(train_samples)} samples across {len(train_ids)} train IDs to {args.train_out}')
    print(f'Wrote {len(val_samples)} samples across {len(val_ids)} val IDs to {args.val_out}')

if __name__ == '__main__':
    main()
