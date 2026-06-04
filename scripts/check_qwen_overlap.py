#!/usr/bin/env python3
import json
from pathlib import Path

def load_ids(path):
    ids=set()
    with open(path,'r',encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line: continue
            j=json.loads(line)
            meta=j.get('metadata') or {}
            if not isinstance(meta, dict):
                # some entries use top-level type/difficulty; try top-level id
                idv=j.get('id') or j.get('ID')
            else:
                idv=meta.get('id')
            if idv:
                ids.add(idv)
    return ids

if __name__ == '__main__':
    train='DATA/qwen_train.jsonl'
    val='DATA/qwen_val.jsonl'
    t=load_ids(train)
    v=load_ids(val)
    print('train_ids:', len(t))
    print('val_ids:', len(v))
    print('overlap:', len(t & v))
    # list a few overlaps
    ov = list(t & v)
    print('overlap sample (10):', ov[:10])
