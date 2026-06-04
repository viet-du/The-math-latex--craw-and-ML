#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def coverage(path):
    p=Path(path)
    total=0
    miss_type=0
    miss_diff=0
    ids=set()
    with p.open('r',encoding='utf-8') as f:
        for line in f:
            line=line.strip()
            if not line: continue
            total+=1
            j=json.loads(line)
            meta=j.get('metadata') or {}
            if not isinstance(meta, dict):
                meta = {}
            if not meta.get('type'):
                miss_type+=1
            if not meta.get('difficulty'):
                miss_diff+=1
            idv=meta.get('id') or j.get('id')
            if idv:
                ids.add(idv)
    print(path, 'samples=', total, 'unique_ids=', len(ids), 'missing_type=', miss_type, 'missing_diff=', miss_diff)

if __name__=='__main__':
    for p in sys.argv[1:]:
        coverage(p)
