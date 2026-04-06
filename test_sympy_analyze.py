import json

try:
    import sympy
    from sympy.parsing.latex import parse_latex
    from sympy.parsing.latex.errors import LaTeXParsingError
except ImportError:
    pass

import sys

def test_sympy_on_dataset():
    try:
        with open('d:/Hoc_tap/The-math-latex--craw-and-ML/formulas/datasheet.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print("Error loading json", e)
        return

    success = 0
    total = 0
    algebra_total = 0
    errors = []

    for item in data:
        if item.get('type') != 'algebra': continue
        algebra_total += 1
        cf = item.get('canonical_form', '')
        if not cf: continue
        total += 1
        try:
            # simple check if there is an equality
            if '=' in cf:
                left, right = cf.split('=', 1)
                expr_l = parse_latex(left)
                expr_r = parse_latex(right)
                eq = sympy.Eq(expr_l, expr_r)
                # sympy.latex(eq)
            else:
                expr = parse_latex(cf)
                sympy.latex(sympy.simplify(expr))
            success += 1
        except Exception as e:
            if len(errors) < 5:
                errors.append((cf, str(e)))

    print(f"Algebra total: {algebra_total}, total eval: {total}, success: {success}")
    print("Sample errors:")
    for err in errors:
        print(" - ", err[0], " : ", err[1])

if __name__ == '__main__':
    test_sympy_on_dataset()
