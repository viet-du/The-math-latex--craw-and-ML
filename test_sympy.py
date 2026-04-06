import json
import sympy
from sympy.parsing.latex import parse_latex

# Check if antlr4 is installed
try:
    import antlr4
except ImportError:
    print("antlr4 not installed")

with open('d:/Hoc_tap/The-math-latex--craw-and-ML/formulas/datasheet.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data[:10]:
    cf = item.get('canonical_form', '')
    print(f"Original: {cf}")
    try:
        expr = parse_latex(cf)
        simplified = sympy.simplify(expr)
        print(f"SymPy:    {sympy.latex(simplified)}")
    except Exception as e:
        print(f"Error:    {e}")
    print("-" * 40)
