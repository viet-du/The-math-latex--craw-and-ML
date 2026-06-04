import json
from pathlib import Path
from copy import deepcopy

p = Path(__file__).resolve().parent.parent / 'formulas' / 'datasheet.json'
backup = p.with_suffix('.json.bak')

print('Loading', p)
with p.open('r', encoding='utf-8') as f:
    data = json.load(f)

backup.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print('Backup written to', backup)

modified = []
manual_review = set()

def normalize_steps(entry):
    steps = entry.get('steps', [])
    if not isinstance(steps, list):
        steps = []
    # clean strings
    clean = []
    seen = set()
    for s in steps:
        if not isinstance(s, str):
            continue
        s2 = s.strip()
        if not s2:
            continue
        if s2 in seen:
            continue
        seen.add(s2)
        clean.append(s2)
    # if not exactly 5, attempt to construct/pad
    if len(clean) == 5:
        entry['steps'] = clean
        return False
    instr = entry.get('instruction', '').strip()
    inp = entry.get('input', '').strip()
    templates = [
        f"Xác định dữ kiện: {inp or instr}",
        "Áp dụng công thức hoặc phép biến đổi phù hợp với đề bài.",
        "Thực hiện các phép biến đổi đại số/tính toán từng bước để tiến tới kết quả.",
        "Kiểm tra điều kiện miền xác định và giả thiết (nếu có).",
        "Viết kết quả cuối cùng ở dạng LaTeX chuẩn và rút gọn nếu cần."
    ]
    new_steps = clean.copy()
    for t in templates:
        if len(new_steps) >= 5:
            break
        if t not in new_steps:
            new_steps.append(t)
    # if still empty, create generic five
    if not new_steps:
        new_steps = templates[:5]
    entry['steps'] = new_steps
    # flag for review if we changed from non-empty original
    if clean and clean != new_steps:
        return True
    return True if not clean else False


def normalize_examples(entry):
    exs = entry.get('example_problems', [])
    if not isinstance(exs, list):
        exs = []
    new = []
    changed = False
    for ex in exs:
        if not isinstance(ex, dict):
            manual_review.add(entry.get('id'))
            continue
        iv = ex.get('input_values', {})
        out = ex.get('output')
        # try to salvage if input values embedded at top-level of ex
        if (not isinstance(iv, dict) or not iv) and any(k for k in ex.keys() if k not in ('input_values','output')):
            iv = {}
            for k,v in ex.items():
                if k in ('input_values','output'):
                    continue
                if isinstance(v, (int, float, str)):
                    iv[k] = v
        if not isinstance(iv, dict):
            iv = {}
        if out is None:
            out = ex.get('result') or ex.get('answer') or None
        ex_clean = {'input_values': iv}
        if out is not None:
            ex_clean['output'] = out
        else:
            ex_clean['output'] = 'TO_FIX'
            manual_review.add(entry.get('id'))
        new.append(ex_clean)
        if ex_clean != ex:
            changed = True
    entry['example_problems'] = new
    return changed

for entry in data:
    eid = entry.get('id')
    changed_any = False
    try:
        s_changed = normalize_steps(entry)
        e_changed = normalize_examples(entry)
        if s_changed or e_changed:
            modified.append(eid)
            changed_any = True
    except Exception as exc:
        print('Error processing', eid, exc)
        manual_review.add(eid)

# write back
p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print('Wrote normalized datasheet.json')
print('Entries scanned:', len(data))
print('Entries modified:', len(modified))
if modified:
    print('Modified ids (sample 50):', modified[:50])
if manual_review:
    print('Needs manual review (sample 50):', list(manual_review)[:50])
else:
    print('No manual-review items detected')
