import json
import logging
import os
import sys

try:
    import sympy
    from sympy.parsing.latex import parse_latex
except ImportError:
    print("SymPy or antlr4 is missing. Please run `pip install sympy antlr4-python3-runtime`")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def parse_and_simplify(latex_str):
    expr = parse_latex(latex_str)
    simplified = sympy.simplify(expr)
    return sympy.latex(simplified)

def process_latex_string(latex_str):
    try:
        if "=" in latex_str:
            parts = latex_str.split("=")
            if len(parts) == 2:
                left = parse_and_simplify(parts[0])
                right = parse_and_simplify(parts[1])
                return (True, f"{left} = {right}")
            else:
                return (True, parse_and_simplify(latex_str))
        else:
            return (True, parse_and_simplify(latex_str))
    except Exception as e:
        return (False, str(e))

def main():
    json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'formulas', 'datasheet.json'))
    log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sympy_errors.log'))

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logging.error(f"Failed to load dataset: {e}")
        return

    # Clear previous error log
    open(log_path, 'w', encoding='utf-8').close()

    success_count = 0
    fail_count = 0
    skip_count = 0
    
    # We maintain a list of known hanging formulas if any
    blacklist = []

    tasks = [(idx, item['canonical_form']) for idx, item in enumerate(data) 
             if item.get('type') == 'algebra' and item.get('canonical_form')]

    logging.info(f"Loaded {len(data)} formulas. Algebra formulas to process: {len(tasks)}.")

    for count, (idx, cf) in enumerate(tasks):
        item = data[idx]
        item_id = item.get('id')
        
        if item_id in blacklist:
            logging.warning(f"Skipping blacklisted ID: {item_id}")
            continue
            
        logging.info(f"Processing ({count+1}/{len(tasks)}): {item_id}")
        
        success, result = process_latex_string(cf)
        if success:
            item['sympy_canonical_form'] = result
            success_count += 1
            logging.info(f"  -> SUCCESS: {result}")
        else:
            fail_count += 1
            logging.warning(f"  -> FAILED: {result}")
            with open(log_path, 'a', encoding='utf-8') as ef:
                ef.write(f"ID: {item_id}\nFormula: {cf}\nError: {result}\n{'-'*40}\n")
                
    # Save the updated JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    logging.info(f"Done. Processed (Success): {success_count}, Failed: {fail_count}, Skipped (Non-algebra): {len(data) - len(tasks)}")

if __name__ == '__main__':
    main()
