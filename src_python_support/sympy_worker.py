import sys
try:
    import sympy
    from sympy.parsing.latex import parse_latex
except ImportError:
    sys.exit(1)

def parse_and_simplify(latex_str):
    expr = parse_latex(latex_str)
    simplified = sympy.simplify(expr)
    return sympy.latex(simplified)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(1)
        
    latex_str = sys.argv[1]
    try:
        if "=" in latex_str:
            parts = latex_str.split("=")
            if len(parts) == 2:
                left = parse_and_simplify(parts[0])
                right = parse_and_simplify(parts[1])
                print(f"{left} = {right}")
            else:
                res = parse_and_simplify(latex_str)
                print(res)
        else:
            res = parse_and_simplify(latex_str)
            print(res)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(3)
