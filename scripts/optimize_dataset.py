"""
Optimized Dataset Fix
====================
1. Normalize category names (geom/geometry → geometry)
2. Generate more samples for small categories
3. Re-split with proper balance
4. Ensure every category in train/val/test

Usage:
    python scripts/optimize_dataset.py
"""

import json
import random
import hashlib
from pathlib import Path
from collections import defaultdict
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# =============================================================================
# CATEGORY NORMALIZATION
# =============================================================================

CATEGORY_MAP = {
    # Geometry variants
    'geom': 'geometry',
    'geo': 'geometry',
    'geometry': 'geometry',
    
    # Linear algebra
    'linalg': 'linear_algebra',
    'la': 'linear_algebra',
    
    # Algebra
    'alg': 'algebra',
    'algebra': 'algebra',
    
    # Machine learning
    'ml': 'machine_learning',
    'machine_learning': 'machine_learning',
    
    # Deep learning
    'dl': 'deep_learning',
    'deep_learning': 'deep_learning',
    
    # Calculus variants
    'calc': 'calculus',
    'calculus': 'calculus',
    'integral': 'calculus',
    'integration': 'calculus',
    'definite': 'calculus',
    
    # Probability/Statistics
    'prob': 'probability',
    'probability': 'probability',
    'ps': 'probability_statistics',
    'probability_statistics': 'probability_statistics',
    'stat': 'statistics',
    'statistics': 'statistics',
    
    # Other math
    'math': 'math',
    'trig': 'trigonometry',
    'trigonometry': 'trigonometry',
    'opt': 'optimization',
    'optimization': 'optimization',
    'dsa': 'data_structures_algorithms',
    'data_structures_algorithms': 'data_structures_algorithms',
    'is': 'information_security',
    'information_security': 'information_security',
    'set': 'sets',
    'sets': 'sets',
    'seq': 'sequences',
    'sequences': 'sequences',
    'special': 'special_functions',
    'special_functions': 'special_functions',
    'gaussian': 'gaussian',
    'fraction': 'fraction',
    'ratio': 'ratio',
    'motion': 'motion',
    'percentage': 'percentage',
    'comb': 'combinatorics',
    'combinatorics': 'combinatorics',
    'complex': 'complex',
    'rl': 'reinforcement_learning',
    'reinforcement_learning': 'reinforcement_learning',
}


# =============================================================================
# TEMPLATES FOR SMALL CATEGORIES (to boost samples)
# =============================================================================

SMALL_CATEGORY_TEMPLATES = {
    'geometry': [
        ("Tinh dien tich hinh tron ban kinh {r} cm (pi = 3.14).", "3.14 * r * r"),
        ("Hinh chu nhat co chieu dai {l} cm, chieu rong {w} cm. Tinh chu vi.", "2 * (l + w)"),
        ("Tam giac co day {b} cm, chieu cao {h} cm. Tinh dien tich.", "0.5 * b * h"),
        ("Tinh dien tich hinh vuong canh {s} cm.", "s * s"),
    ],
    'fraction': [
        ("Tinh hieu: {a}/{d} - {b}/{d}", "(a - b) / d"),
        ("Tinh tong: {a}/{d} + {b}/{d}", "(a + b) / d"),
        ("Nhan phan so: ({a}/{d}) * ({b}/{e})", "a * b / (d * e)"),
    ],
    'ratio': [
        ("Chia {total} theo ti le {a}:{b}:{c}. Tinh moi phan.", "total * a / (a+b+c), ..."),
        ("So A gap {n} lan so B. Bieu dien ti le A:B.", "n:1"),
    ],
    'percentage': [
        ("{p}% cua {x} la bao nhieu?", "x * p / 100"),
        ("Mot san pham gia {price} dong, giam gia {p}%. Gia moi?", "price * (100 - p) / 100"),
    ],
    'combinatorics': [
        ("Tinh C({n},{k}) = n! / (k!(n-k)!)", "n! / (k! * (n-k)!)"),
        ("Tinh P({n},{r}) = n! / (n-r)!", "n! / (n-r)!"),
    ],
    'trigonometry': [
        ("Tinh sin({a}deg) + cos({a}deg) voi {a} = 45", "sin(a) + cos(a)"),
        ("Giai tam giac ABC biet a={a}, A={A}deg, B={B}deg.", "tim canh/bieu thuc"),
    ],
    'probability': [
        ("Xac suat lay duoc bi do trong hop co {n} bi do va {m} bi trang.", "n / (n + m)"),
        (" Tung xu {n} lan. Tinh xac suat mat mat nhieu nhat {k} lan.", "P(X <= k)"),
    ],
    'motion': [
        ("Xe di tu A den B voi van toc {v} km/h trong {t} h. Tinh quang duong.", "v * t"),
        ("Hai xe cach nhau {d} km, di nguoc chieu voi van toc {v1} va {v2}. Gap nhau sau?", "d / (v1 + v2)"),
    ],
    'sequences': [
        ("Cho day so: {a1}, {a2}, {a3},... Tim so thu {n}.", "a1 + (n-1)*d"),
        ("Day so 1, 2, 4, 8,... Tim so thu {n}.", "2^(n-1)"),
    ],
    'sets': [
        ("Tap hop A = {{{a1}, {a2}}} va B = {{{b1}, {b2}}}. Tim A ∪ B.", "A hop B"),
        ("Cho A ⊂ B, |A| = {na}, |B| = {nb}. Tim |B\\A|.", "nb - na"),
    ],
    'optimization': [
        ("Tim gia tri lon nhat cua y = -{x}^2 + {a}x + {b}.", "-b/(2a)"),
        ("Tim gia tri nho nhat cua f(x) = (x - {h})^2 + {k}.", "h, k"),
    ],
}


def generate_samples_for_category(category, target_count, existing_count):
    """Generate more samples for a category"""
    needed = max(0, target_count - existing_count)
    if needed == 0 or category not in SMALL_CATEGORY_TEMPLATES:
        return []
    
    templates = SMALL_CATEGORY_TEMPLATES[category]
    samples = []
    
    # Generate samples using templates
    random.seed(42)
    for i in range(needed):
        template_text, formula = random.choice(templates)
        
        # Generate random values
        if '{r}' in template_text:
            r = random.randint(5, 20)
            text = template_text.replace('{r}', str(r))
            answer = round(3.14 * r * r, 2)
        elif '{l}' in template_text:
            l = random.randint(10, 50)
            w = random.randint(5, 30)
            text = template_text.replace('{l}', str(l)).replace('{w}', str(w))
            answer = 2 * (l + w)
        elif '{b}' in template_text and '{h}' in template_text:
            b = random.randint(10, 40)
            h = random.randint(5, 25)
            text = template_text.replace('{b}', str(b)).replace('{h}', str(h))
            answer = 0.5 * b * h
        elif '{s}' in template_text:
            s = random.randint(5, 30)
            text = template_text.replace('{s}', str(s))
            answer = s * s
        elif '{a}' in template_text and '{d}' in template_text:
            a = random.randint(1, 9)
            b = random.randint(1, a) if 'hieu' in template_text.lower() else random.randint(1, 9)
            d = random.randint(2, 10)
            text = template_text.replace('{a}', str(a)).replace('{b}', str(b)).replace('{d}', str(d))
            answer = f"(a - b) / d" if 'hieu' in template_text.lower() else f"(a + b) / d"
        elif '{p}' in template_text and '{x}' in template_text:
            p = random.randint(10, 50)
            x = random.randint(100, 1000)
            text = template_text.replace('{p}', str(p)).replace('{x}', str(x))
            answer = x * p / 100
        elif '{n}' in template_text:
            n = random.randint(3, 10)
            text = template_text.replace('{n}', str(n))
            answer = 1  # Simplified
        else:
            text = template_text
            answer = "formula"
        
        samples.append({
            'id': f'gen_{category}_{i}',
            'problem': text,
            'category': category,
            'subcategory': category,
            'solution_steps': [f"Ap dung: {formula}"],
            'answer': str(answer),
            'difficulty': 'medium',
            'source': 'generated',
            'is_generated': True,
        })
    
    return samples


# =============================================================================
# LOAD AND NORMALIZE
# =============================================================================

def load_data():
    """Load all existing data"""
    all_data = []
    
    for split in ['train', 'val', 'test']:
        filepath = f"DATA/5agent_final/{split}/agent1.jsonl"
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    # Extract category from ID
                    entry_id = data.get('id', '')
                    parts = entry_id.split('_')
                    
                    # Find original category
                    if len(parts) >= 2:
                        orig_cat = parts[1]
                        norm_cat = CATEGORY_MAP.get(orig_cat, orig_cat)
                    else:
                        norm_cat = 'unknown'
                    
                    data['normalized_category'] = norm_cat
                    data['original_category'] = orig_cat
                    data['split'] = split
                    all_data.append(data)
    
    return all_data


def main():
    print("=" * 70)
    print("OPTIMIZE DATASET - FIX IMBALANCE")
    print("=" * 70)
    
    # Step 1: Load existing data
    print("\n📦 Step 1: Loading existing data...")
    all_data = load_data()
    print(f"   Total loaded: {len(all_data)}")
    
    # Step 2: Count by category
    print("\n📊 Step 2: Analyzing categories...")
    category_counts = defaultdict(lambda: {'train': 0, 'val': 0, 'test': 0})
    
    for item in all_data:
        cat = item['normalized_category']
        split = item['split']
        category_counts[cat][split] += 1
    
    # Print before
    print("\n   BEFORE - Category counts:")
    print(f"   {'Category':<25} {'Train':>8} {'Val':>8} {'Test':>8} {'Total':>8}")
    print("   " + "-" * 65)
    for cat in sorted(category_counts.keys()):
        counts = category_counts[cat]
        total = sum(counts.values())
        flag = " ⚠️" if counts['val'] == 0 or counts['test'] == 0 else ""
        print(f"   {cat:<25} {counts['train']:>8} {counts['val']:>8} {counts['test']:>8} {total:>8}{flag}")
    
    # Step 3: Generate more samples for small categories
    print("\n🧪 Step 3: Generating samples for small categories...")
    
    MIN_PER_SPLIT = 3  # Minimum samples per split
    TARGET_TOTAL = 50  # Target per category
    
    new_samples = []
    
    for cat, counts in category_counts.items():
        total = sum(counts.values())
        
        # Check if needs more
        needs_more = False
        for split in ['train', 'val', 'test']:
            if counts[split] < MIN_PER_SPLIT:
                needs_more = True
                break
        
        if needs_more or total < TARGET_TOTAL:
            samples = generate_samples_for_category(cat, TARGET_TOTAL, total)
            new_samples.extend(samples)
            print(f"   {cat}: generating {len(samples)} samples")
    
    print(f"   Total new samples: {len(new_samples)}")
    
    # Step 4: Combine and re-split
    print("\n✂️ Step 4: Re-splitting with balance...")
    
    # Create combined dataset
    combined = []
    
    # Add original data (reset split for re-splitting)
    for item in all_data:
        combined.append({
            'id': item['id'],
            'problem': item['problem'],
            'category': item['normalized_category'],
            'subcategory': item['subcategory'],
            'solution_steps': item.get('solution_steps', []),
            'answer': item.get('answer', ''),
            'difficulty': item.get('difficulty', 'medium'),
            'source': item.get('source', 'original'),
        })
    
    # Add new samples
    for sample in new_samples:
        combined.append({
            'id': sample['id'],
            'problem': sample['problem'],
            'category': sample['category'],
            'subcategory': sample['subcategory'],
            'solution_steps': sample['solution_steps'],
            'answer': sample['answer'],
            'difficulty': sample['difficulty'],
            'source': sample['source'],
        })
    
    print(f"   Total before split: {len(combined)}")
    
    # Split by category for balance
    by_category = defaultdict(list)
    for item in combined:
        by_category[item['category']].append(item)
    
    train_data, val_data, test_data = [], [], []
    
    for cat, items in by_category.items():
        random.shuffle(items)
        n = len(items)
        n_train = max(MIN_PER_SPLIT, int(n * 0.8))
        n_val = max(MIN_PER_SPLIT, int(n * 0.1))
        # Ensure minimum in test
        n_test = n - n_train - n_val
        if n_test < MIN_PER_SPLIT and n >= MIN_PER_SPLIT * 3:
            n_test = MIN_PER_SPLIT
            n_train = n - n_val - n_test
        
        train_data.extend(items[:n_train])
        val_data.extend(items[n_train:n_train + n_val])
        test_data.extend(items[n_train + n_val:])
    
    print(f"   Train: {len(train_data)}")
    print(f"   Val:   {len(val_data)}")
    print(f"   Test:  {len(test_data)}")
    
    # Step 5: Verify balance
    print("\n✅ Step 5: Verifying balance...")
    
    new_category_counts = defaultdict(lambda: {'train': 0, 'val': 0, 'test': 0})
    
    for item in train_data:
        new_category_counts[item['category']]['train'] += 1
    for item in val_data:
        new_category_counts[item['category']]['val'] += 1
    for item in test_data:
        new_category_counts[item['category']]['test'] += 1
    
    print("\n   AFTER - Category counts:")
    print(f"   {'Category':<25} {'Train':>8} {'Val':>8} {'Test':>8} {'Total':>8}")
    print("   " + "-" * 65)
    
    issues = []
    for cat in sorted(new_category_counts.keys()):
        counts = new_category_counts[cat]
        total = sum(counts.values())
        
        # Check for issues
        if counts['val'] == 0 or counts['test'] == 0:
            issues.append(cat)
            flag = " ❌"
        elif abs(counts['train']/total - 0.8) > 0.3:
            flag = " ⚠️"
        else:
            flag = " ✓"
        
        print(f"   {cat:<25} {counts['train']:>8} {counts['val']:>8} {counts['test']:>8} {total:>8}{flag}")
    
    # Step 6: Export
    print("\n💾 Step 6: Exporting...")
    
    output_dir = Path("DATA/5agent_final_balanced")
    output_dir.mkdir(exist_ok=True)
    
    for split_name, data in [('train', train_data), ('val', val_data), ('test', test_data)]:
        split_dir = output_dir / split_name
        split_dir.mkdir(exist_ok=True)
        
        # Export for each agent (just agent1 has category info, others can use same)
        for agent_id in ['agent1', 'agent2', 'agent3', 'agent4', 'agent5']:
            filepath = split_dir / f"{agent_id}.jsonl"
            with open(filepath, 'w', encoding='utf-8') as f:
                for item in data:
                    # Create format for 5-agent
                    output = {
                        'id': f"{item['id']}_{agent_id}",
                        'messages': [
                            {'role': 'user', 'content': item['problem']},
                        ]
                    }
                    f.write(json.dumps(output, ensure_ascii=False) + '\n')
        
        print(f"   {split_name}: {len(data)} samples")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n📁 Output: {output_dir}")
    print(f"   Train: {len(train_data)}")
    print(f"   Val:   {len(val_data)}")
    print(f"   Test:  {len(test_data)}")
    
    if issues:
        print(f"\n⚠️ Categories still missing splits:")
        for cat in issues:
            counts = new_category_counts[cat]
            print(f"   - {cat}: train={counts['train']}, val={counts['val']}, test={counts['test']}")
    else:
        print("\n✅ All categories have samples in train/val/test!")


if __name__ == "__main__":
    main()
