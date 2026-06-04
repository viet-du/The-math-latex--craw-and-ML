#!/usr/bin/env python3
import json
from pathlib import Path
import sys

def stats(path):
    ids=set(); samples=0
    p=Path(path)
    if not p.exists():
        return 0,0
    with p.open('r',encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line: continue
            j=json.loads(line)
            samples += 1
            meta=j.get('metadata') or {}
            idv = None
            if isinstance(meta, dict):
                idv = meta.get('id')
            if not idv:
                idv = j.get('id')
            if idv:
                ids.add(idv)
    return samples, len(ids)

if __name__=='__main__':
    files = sys.argv[1:]
    for f in files:
        s,i = stats(f)
        print(f, 'samples=', s, 'unique_ids=', i)
