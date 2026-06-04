import collections
import json
import re
from pathlib import Path


path = Path("formulas/datasheet.json")
data = json.loads(path.read_text(encoding="utf-8-sig"))


def joined(item, field):
    value = item.get(field)
    if isinstance(value, list):
        return " ".join(str(x) for x in value)
    return str(value or "")


def all_text(item):
    parts = [
        item.get("id", ""),
        item.get("instruction", ""),
        item.get("input", ""),
        item.get("output", ""),
        item.get("canonical_form", ""),
        " ".join(item.get("tags", []) or []),
    ]
    return " ".join(str(x) for x in parts).lower()


probability = []
fraction = []
bad_prob_steps = []
bad_fraction_steps = []
bad_examples = collections.Counter()
bad_example_ids = collections.defaultdict(list)
step_lengths = collections.Counter()
types = collections.Counter()
tags = collections.Counter()

bad_patterns = {
    "sympy_set_tokens": re.compile(r"\\left| cap | cup | mid |\\right"),
    "bound_index_replaced": re.compile(r"\b\d+_i\b"),
    "differential_replaced": re.compile(r"\bd\d+\b"),
    "placeholder_variable_only": re.compile(r'^\s*\\?[A-Za-z]?\s*$'),
    "to_fix": re.compile(r"TO_FIX"),
}

for item in data:
    text = all_text(item)
    steps = joined(item, "steps").lower()
    types[item.get("type")] += 1
    for tag in item.get("tags", []) or []:
        tags[tag] += 1
    step_lengths[len(item.get("steps") or [])] += 1

    if "probability" in (item.get("tags") or []) or "xác suất" in text or "bayes" in text:
        probability.append(item)
        if any(word in steps for word in ["tử số", "mẫu số", "phân số", "quy đồng"]):
            bad_prob_steps.append(item.get("id"))

    if "fraction" in (item.get("tags") or []) or "phân số" in text or "fraction" in text:
        fraction.append(item)
        if any(word in steps for word in ["xác suất", "không gian mẫu", "biến cố", "kỳ vọng"]):
            bad_fraction_steps.append(item.get("id"))

    for ex in item.get("example_problems") or []:
        out = str(ex.get("output", ""))
        for name, pattern in bad_patterns.items():
            if pattern.search(out):
                bad_examples[name] += 1
                if len(bad_example_ids[name]) < 15:
                    bad_example_ids[name].append((item.get("id"), out))

print("records", len(data))
print("types", types.most_common())
print("top_tags", tags.most_common(30))
print("step_lengths", step_lengths.most_common())
print("probability_records", len(probability))
print("fraction_records", len(fraction))
print("bad_prob_steps", len(bad_prob_steps), bad_prob_steps[:30])
print("bad_fraction_steps", len(bad_fraction_steps), bad_fraction_steps[:30])
print("bad_examples", bad_examples)
for name, rows in bad_example_ids.items():
    print("bad_example_sample", name)
    for row in rows:
        print(row)
