#!/usr/bin/env python3
"""
Prepare and clean DATA/datasheet.json for instruction fine-tuning.
Outputs a JSONL file with one object per line containing:
  - instruction: short instruction text
  - input: optional input/context text (can be empty string)
  - output: expected answer (LaTeX)
  - metadata: {id, tags, difficulty}

Usage:
  python scripts/prepare_finetune_dataset.py --input DATA/datasheet.json --output DATA/cleaned_finetune.jsonl --augment

Options:
  --augment    : emit additional entries using instruction_variants and input_variants
  --examples   : include example_problems as separate entries (fills variables)
  --dedupe     : deduplicate by canonical_form (default: True)

This script is conservative (keeps LaTeX unchanged apart from whitespace/char normalization).
"""

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Any, List, Set

# Optional SymPy normalization
try:
    import sympy as sp
    from sympy import sympify
    from sympy.parsing.latex import parse_latex
    HAS_SYMPY = True
except Exception:
    HAS_SYMPY = False


def normalize_whitespace(s: str) -> str:
    s = s.replace('\r\n', '\n')
    s = s.replace('\t', ' ')
    # collapse multiple spaces
    s = re.sub(r"[ ]+", ' ', s)
    # collapse multiple newlines
    s = re.sub(r"\n{2,}", '\n', s)
    return s.strip()


def normalize_latex(s: str) -> str:
    if s is None:
        return ''
    # Normalize unicode (e.g. different minus signs)
    s = unicodedata.normalize('NFKC', s)
    # Replace unicode minus or long dash with normal hyphen
    s = s.replace('\u2212', '-')
    s = s.replace('\u2013', '-')
    s = s.replace('\u2014', '-')
    # common smart quotes -> ascii
    s = s.replace('“', '"').replace('”', '"').replace("‘", "'").replace("’", "'")
    s = normalize_whitespace(s)
    return s


def normalize_with_sympy(s: str) -> (str, bool):
    """Try to parse LaTeX or plain math expression with SymPy and return normalized LaTeX.
    Returns (latex_str, success_flag).
    Falls back gracefully if SymPy not available or parsing fails.
    """
    if not HAS_SYMPY or not s:
        return s, False

    txt = s
    # strip common LaTeX wrappers
    txt = txt.strip()
    if txt.startswith('$$') and txt.endswith('$$'):
        txt = txt[2:-2].strip()
    if txt.startswith('$') and txt.endswith('$'):
        txt = txt[1:-1].strip()

    # helper: convert simple \frac{a}{b} to (a)/(b) iteratively
    def _frac_to_div(text: str) -> str:
        pattern = re.compile(r"\\frac\s*{([^{}]+)}\s*{([^{}]+)}")
        prev = None
        cur = text
        while prev != cur:
            prev = cur
            cur = pattern.sub(r'(\1)/(\2)', cur)
        return cur

    try:
        # try parsing as LaTeX first
        expr = None
        try:
            expr = parse_latex(txt)
        except Exception:
            # fallback: replace \frac and try sympify
            prepared = _frac_to_div(txt)
            expr = sympify(prepared)

        expr_s = sp.simplify(expr)
        latex_out = sp.latex(expr_s)
        return latex_out, True
    except Exception:
        return s, False


def make_entry(instruction: str, input_text: str, output: str, meta: Dict[str,Any]) -> Dict[str,Any]:
    return {
        'instruction': normalize_latex(instruction or ''),
        'input': normalize_latex(input_text or ''),
        'output': normalize_latex(output or ''),
        'metadata': meta,
    }


def substitute_example_input(template: str, variables_map: Dict[str,str], example_values: Dict[str,Any]) -> str:
    # variables_map: key -> symbol (e.g. 'numerator_1' -> 'a')
    s = template
    # perform simple replacements for each variable symbol
    for key, sym in variables_map.items():
        if key in example_values:
            val = example_values[key]
            # convert floats/ints to string, keep sign
            val_s = str(val)
            # replace occurrences of the symbol as standalone or in LaTeX braces
            s = re.sub(rf"\b{re.escape(sym)}\b", (lambda m, vs=val_s: vs), s)
            # replace inside braces {a} -> {5}
            s = s.replace('{' + sym + '}', '{' + val_s + '}')
    return s


def load_json(path: Path) -> List[Dict[str,Any]]:
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def write_jsonl(path: Path, objects: List[Dict[str,Any]]):
    with path.open('w', encoding='utf-8') as f:
        for obj in objects:
            f.write(json.dumps(obj, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i', default='DATA/datasheet.json')
    parser.add_argument('--output', '-o', default='DATA/cleaned_finetune.jsonl')
    parser.add_argument('--augment', action='store_true', help='Emit variants from instruction_variants and input_variants')
    parser.add_argument('--examples', action='store_true', help='Emit example_problems as separate entries')
    parser.add_argument('--dedupe', action='store_true', default=True, help='Deduplicate by canonical_form')
    parser.add_argument('--sympy', action='store_true', help='Use SymPy to normalize outputs (requires sympy)')
    parser.add_argument('--export-qwen', action='store_true', help='Export Qwen chat-format JSONL with CoT')
    parser.add_argument('--train-output', default='DATA/train.jsonl', help='Train output path when exporting Qwen format')
    parser.add_argument('--val-output', default='DATA/val.jsonl', help='Validation output path when exporting Qwen format')
    parser.add_argument('--val-size', type=float, default=0.05, help='Fraction of data to hold out for validation')
    parser.add_argument('--max-instr-variants', type=int, default=6, help='Max instruction_variants to use per item')
    parser.add_argument('--max-input-variants', type=int, default=4, help='Max input_variants to use per item')
    parser.add_argument('--max-examples-per-item', type=int, default=5, help='Max example_problems to emit per item')
    args = parser.parse_args()

    inp = Path(args.input)
    out = Path(args.output)

    if not inp.exists():
        print(f'Input file {inp} not found')
        return

    data = load_json(inp)
    out_entries: List[Dict[str,Any]] = []
    seen_canonical: Set[str] = set()

    for item in data:
        item_id = item.get('id')
        instruction = item.get('instruction') or (item.get('instruction_variants') or [None])[0]
        input_text = item.get('input') or ''
        # prefer output_corrected, then canonical_form, then output
        output = item.get('output_corrected') or item.get('canonical_form') or item.get('output') or ''
        canonical = item.get('output_corrected') or item.get('canonical_form') or item.get('output') or ''

        # optionally normalize using SymPy
        sympy_normalized = False
        if args.sympy and canonical:
            norm_out, ok = normalize_with_sympy(canonical)
            if ok:
                canonical = norm_out
                sympy_normalized = True

        if not canonical or not instruction:
            # skip incomplete
            continue

        meta = {
            'id': item_id,
            'type': item.get('type'),
            'difficulty': item.get('difficulty'),
            'tags': item.get('tags'),
            'sympy_normalized': sympy_normalized,
        }

        # base entry
        if args.dedupe:
            key = normalize_latex(canonical)
            if key not in seen_canonical:
                seen_canonical.add(key)
                out_entries.append(make_entry(instruction, input_text, canonical, meta))
        else:
            out_entries.append(make_entry(instruction, input_text, canonical, meta))

        # augmentation: expand instruction_variants x input_variants combinations
        if args.augment:
            instr_variants = item.get('instruction_variants', [])[:args.max_instr_variants]
            input_variants = item.get('input_variants', [])[:args.max_input_variants]
            # combine
            for iv in instr_variants:
                for inp_var in input_variants or [input_text]:
                    instr_text = iv or instruction
                    inp_text = inp_var or input_text
                    if args.dedupe:
                        key = normalize_latex(canonical) + '|' + normalize_latex(instr_text) + '|' + normalize_latex(inp_text)
                        if key in seen_canonical:
                            continue
                        seen_canonical.add(key)
                    out_entries.append(make_entry(instr_text, inp_text, canonical, meta))

        # include example problems by substituting variables
        if args.examples and 'example_problems' in item and item.get('variables'):
            variables_map = item.get('variables')  # maps keys like "numerator_1" -> 'a'
            for ex in item.get('example_problems', [])[:args.max_examples_per_item]:
                vals = ex.get('input_values') or {}
                substituted_input = substitute_example_input(input_text, variables_map, vals)
                ex_output = ex.get('output') or canonical
                out_entries.append(make_entry(instruction, substituted_input, ex_output, meta))

        # store original item for later qwen export (keep full fields)
        item['_prepared_meta'] = meta
        item['_prepared_canonical'] = canonical
        item['_prepared_instruction'] = instruction
        item['_prepared_input'] = input_text

    # final normalization: ensure outputs are non-empty
    filtered = [e for e in out_entries if e['output'].strip()]

    # if not exporting qwen-format, write the simple cleaned file
    if not args.export_qwen:
        write_jsonl(out, filtered)
        print(f'Wrote {len(filtered)} entries to {out}')
        return

    # Build Qwen chat-format entries with CoT
    qwen_entries: List[Dict[str,Any]] = []
    for item in data:
        # require prepared fields
        canonical = item.get('_prepared_canonical')
        instruction = item.get('_prepared_instruction')
        input_text = item.get('_prepared_input')
        meta = item.get('_prepared_meta') or {}
        if not canonical or not instruction:
            continue

        steps = item.get('steps') or []
        reasoning = item.get('reasoning') or ''

        # choose variants
        instr_vars = ([instruction] + item.get('instruction_variants', []) )[:args.max_instr_variants]
        input_vars = ([input_text] + item.get('input_variants', []))[:args.max_input_variants]

        for instr in instr_vars:
            for inp in input_vars:
                # build assistant content: steps + reasoning + final boxed canonical
                assistant_parts: List[str] = []
                for i, st in enumerate(steps, start=1):
                    assistant_parts.append(f"**Bước {i}:** {st}")
                if reasoning:
                    assistant_parts.append(reasoning)
                # ensure canonical rendered inside boxed math
                boxed = f"$$\\boxed{{{canonical}}}$$"
                assistant_parts.append(f"Vậy: {boxed}")
                assistant_content = '\n'.join(assistant_parts)

                messages = [
                    {'role': 'system', 'content': 'Bạn là trợ lý toán học. Hãy giải từng bước và đưa kết quả cuối bằng LaTeX chuẩn trong \\boxed{}.'},
                    {'role': 'user', 'content': (instr + ('\n' + inp if inp else ''))},
                    {'role': 'assistant', 'content': assistant_content},
                ]

                qwen_entries.append({'messages': messages, 'metadata': meta})

    # split into train/val
    import random
    random.seed(42)
    random.shuffle(qwen_entries)
    n = len(qwen_entries)
    val_n = max(1, int(n * args.val_size))
    val = qwen_entries[:val_n]
    train = qwen_entries[val_n:]

    write_jsonl(Path(args.train_output), train)
    write_jsonl(Path(args.val_output), val)
    print(f'Wrote {len(train)} train and {len(val)} val entries to {args.train_output} and {args.val_output}')


if __name__ == '__main__':
    main()
