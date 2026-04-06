#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script v2: Chuyển đổi nâng cao với instruction cụ thể từ formula LaTeX
và biến nhất quán (x là biến chính, a là tham số).

Chạy từ thư mục: D:\Hoc_tap\The-math-latex--craw-and-ML\formulas\
"""

import json
import re
import hashlib
from pathlib import Path

# SymPy: parse LaTeX → chuẩn hoá biểu thức
try:
    from sympy.parsing.latex import parse_latex as _sympy_parse_latex
    import sympy as _sympy
    _SYMPY_AVAILABLE = True
except ImportError:
    _SYMPY_AVAILABLE = False

# ===========================================================================
# SYMPY NORMALIZATION
# ===========================================================================

# Các pattern LaTeX mà SymPy không xử lý được, skip luôn để tránh false parse
_SYMPY_SKIP_PATTERNS = [
    r"\\begin",      # môi trường bảng/matrix
    r"\\end",
    r"\\text{",      # text trong latex
    r"\\mathrm{",
    r"\\mathbf{",
    r"\\nabla",      # gradient – thường là đại số vector
    r"\\partial",   # đạo hàm riêng
    r"\\sum",        # sigma
    r"\\prod",
    r"\\lim",
    r"\\bigcap",
    r"\\bigcup",
    r"\\subset",
    r"\\supset",
    r"\\in\b",
    r"\\notin",
    r"\\Rightarrow",
    r"\\Leftrightarrow",
    r"\\forall",
    r"\\exists",
    r"\\Gamma",      # hàm đặc biệt chưa cần chuẩn hoá
    r"\\Psi",
    r"\\Omega",
    r"H_{",          # Hermite polynomial
    r"\\approx",
    r"\\neq",
    r"\\leq",
    r"\\geq",
    r"\\int_{-\\infty}",  # tích phân vô hạn cần antlr đặc biệt
]


def sympy_normalize_latex(latex_str: str) -> str:
    """
    Chuẩn hoá biểu thức LaTeX qua SymPy.

    Quy trình:
      1. Kiểm tra các pattern phức tạp (vector, set, ODE…) → skip.
      2. parse_latex() → SymPy expression.
      3. simplify() để thu gọn nếu expression không quá dài.
      4. sympy.latex() → chuỗi LaTeX chuẩn của SymPy.
      5. Nếu bất kỳ bước nào thất bại, trả về chuỗi gốc.

    Args:
        latex_str: chuỗi LaTeX thô từ dataset.

    Returns:
        Chuỗi LaTeX đã chuẩn hoá, hoặc chuỗi gốc nếu không parse được.
    """
    if not _SYMPY_AVAILABLE:
        return latex_str

    s = latex_str.strip()
    if not s:
        return latex_str

    # Bỏ qua các dạng SymPy xử lý không tốt
    for pat in _SYMPY_SKIP_PATTERNS:
        if re.search(pat, s):
            return latex_str

    # Bỏ qua nếu chứa nhiều dấu = (đẳng thức, không phải expression đơn)
    if s.count("=") > 1:
        return latex_str

    # Bỏ qua nếu là chuỗi quá ngắn hoặc chỉ là ký hiệu plain text
    if len(s) < 2:
        return latex_str

    try:
        expr = _sympy_parse_latex(s)
        # Không simplify: chỉ re-format cú pháp LaTeX về dạng chuẩn SymPy.
        # simplify() quá chậm và có thể mất thông tin (C, n≠-1, v.v.)
        normalized = _sympy.latex(expr)
        # Không dùng nếu kết quả rỗng hoặc quá ngắn (có thể parse sai)
        if normalized and len(normalized) >= 1:
            # Loại bỏ các kết quả Boolean mà SymPy tự verify thành True/False
            if normalized in (r"\text{True}", r"\text{False}",
                              "True", "False", r"\mathrm{True}", r"\mathrm{False}"):
                return latex_str
            # Nếu kết quả ngắn hơn 30% so với input, có thể đã mất thông tin
            if len(normalized) < len(s) * 0.3:
                return latex_str
            return normalized
    except Exception:
        pass

    return latex_str


# ===========================================================================
# PARSING FORMULA để tạo instruction cụ thể
# ===========================================================================

def parse_integral_instruction(formula):
    """Tạo instruction cụ thể cho tích phân dựa vào nội dung."""
    f = formula.replace("\\\\", "\\").strip()

    # Detect special patterns
    if "\\int u dv" in f or "u dv = uv" in f:
        return "Tích phân từng phần (integration by parts)"
    if "\\int_{-\\infty}^{\\infty}" in f or "\\int _{-\\infty }^{\\infty }" in f:
        return "Tích phân xác định trên toàn trục thực"
    if "e^{ax}" in f or "e^{bx}" in f:
        if "\\cos" in f and "\\sin" in f:
            return "Tính tích phân của hàm mũ nhân hàm lượng giác"
        elif "\\cos" in f:
            return "Tính tích phân \\int e^{bx} \\cos ax \\, dx"
        elif "\\sin" in f:
            return "Tính tích phân \\int e^{bx} \\sin ax \\, dx"
        elif "x^n" in f or "x^2" in f or "x^3" in f:
            return "Tính tích phân của đơn thức nhân hàm mũ"
        else:
            return "Tính tích phân của hàm mũ e^{ax}"
    if "e^{-ax^2}" in f or "e^{ax^2}" in f or "e^{-x^2}" in f:
        return "Tính tích phân Gaussian (hàm mũ dạng bình phương)"
    if "e^{x}" in f or "e^x" in f:
        if "x^" in f:
            return "Tính tích phân của đơn thức nhân hàm mũ e^x"
        return "Tính tích phân \\int e^x \\, dx"
    if "\\ln" in f:
        if "ln ax" in f or "ln (ax" in f:
            return "Tính tích phân của hàm logarit tự nhiên ln(ax)"
        if "ln ( x^2" in f:
            return "Tính tích phân \\int \\ln(x^2 \\pm a^2) \\, dx"
        return "Tính tích phân của hàm logarit tự nhiên"
    if "\\tanh" in f:
        return "Tính tích phân của hàm hyperbol tanh(ax)"
    if "\\cosh" in f and "\\sinh" in f:
        return "Tính tích phân tích của sinh và cosh"
    if "\\cosh" in f:
        return "Tính tích phân của hàm hyperbol cosh(ax)"
    if "\\sinh" in f:
        return "Tính tích phân của hàm hyperbol sinh(ax)"
    if "\\cos^2" in f and "\\sin" in f:
        return "Tính tích phân của tích cos²(ax)·sin(ax)"
    if "\\sin^2" in f and "\\cos^2" in f:
        return "Tính tích phân \\int \\sin^2 ax \\cos^2 ax \\, dx"
    if "\\sin^2 x" in f or "\\sin^2 ax" in f:
        return "Tính tích phân \\int \\sin^2(ax) \\, dx bằng công thức hạ bậc"
    if "\\cos^2 x" in f or "\\cos^2 ax" in f:
        return "Tính tích phân \\int \\cos^2(ax) \\, dx bằng công thức hạ bậc"
    if "\\sin^3" in f:
        return "Tính tích phân \\int \\sin^3(ax) \\, dx"
    if "\\cos^3" in f:
        return "Tính tích phân \\int \\cos^3(ax) \\, dx"
    if "\\sin x" in f or "\\sin ax" in f:
        if "x \\sin" in f:
            return "Tính tích phân \\int x \\sin(ax) \\, dx bằng tích phân từng phần"
        if "x^2 \\sin" in f:
            return "Tính tích phân \\int x^2 \\sin(ax) \\, dx"
        return "Tính tích phân của hàm sin(ax)"
    if "\\cos x" in f or "\\cos ax" in f:
        if "x \\cos" in f:
            return "Tính tích phân \\int x \\cos(ax) \\, dx bằng tích phân từng phần"
        if "x^2 \\cos" in f:
            return "Tính tích phân \\int x^2 \\cos(ax) \\, dx"
        return "Tính tích phân của hàm cos(ax)"
    if "\\csc x" in f or "\\csc^2" in f or "\\csc^3" in f:
        return "Tính tích phân của hàm csc(x) và lũy thừa của nó"
    if "\\sec x" in f and "\\csc x" in f:
        return "Tính tích phân \\int \\sec x \\csc x \\, dx"
    if "\\sec x \\tan" in f:
        return "Tính tích phân \\int \\sec x \\tan x \\, dx"
    if "\\sec^2" in f:
        return "Tính tích phân của hàm sec²(ax)"
    if "\\sec^n" in f:
        return "Tính tích phân \\int \\sec^n x \\tan x \\, dx"
    if "\\sec^3" in f:
        return "Tính tích phân \\int \\sec^3 x \\, dx bằng tích phân từng phần"
    if "\\tan^2" in f:
        return "Tính tích phân \\int \\tan^2(ax) \\, dx"
    if "\\tan^3" in f:
        return "Tính tích phân \\int \\tan^3(ax) \\, dx"
    if "\\tan ax" in f or "\\tan x" in f:
        return "Tính tích phân của hàm tan(ax)"
    if "\\Gamma" in f:
        return "Tính tích phân sử dụng hàm Gamma"
    if "\\sqrt{x^2" in f:
        return "Tính tích phân chứa căn bậc hai \\sqrt{x^2 \\pm a^2}"
    if "\\sqrt{a^2 - x^2}" in f:
        return "Tính tích phân chứa căn bậc hai \\sqrt{a^2 - x^2}"
    if "\\sqrt{ax+b}" in f:
        return "Tính tích phân chứa căn bậc hai \\sqrt{ax+b}"
    if "\\sqrt{x-a}" in f or "\\sqrt{x\\pm a}" in f:
        return "Tính tích phân chứa căn bậc hai \\sqrt{x \\pm a}"
    if "x^n dx" in f or "x^n\\," in f:
        return "Tính tích phân lũy thừa \\int x^n \\, dx"
    if "x(x+a)^n" in f:
        return "Tính tích phân \\int x(x+a)^n \\, dx"
    if "(x+a)^n" in f:
        return "Tính tích phân lũy thừa dịch chuyển \\int (x+a)^n \\, dx"
    if "(ax+b)^{3/2}" in f:
        return "Tính tích phân \\int (ax+b)^{3/2} \\, dx"
    if "1/(x+a)" in f or "\\frac{1}{x+a}" in f or "\\frac{1}{(x+a)" in f:
        if "(x+a)(x+b)" in f or "(x+a)^2" in f:
            return "Tính tích phân phân thức hữu tỉ dạng \\frac{1}{(x+a)^2}"
        return "Tính tích phân phân thức \\frac{1}{x+a}"
    if "\\frac{1}{1+x^2}" in f:
        return "Tính tích phân \\int \\frac{1}{1+x^2} dx = \\arctan x"
    if "\\frac{1}{ax+b}" in f:
        return "Tính tích phân \\int \\frac{1}{ax+b} dx = \\frac{1}{a} \\ln|ax+b|"
    if "\\frac{1}{ax^2+bx+c}" in f:
        return "Tính tích phân phân thức bậc hai \\int \\frac{1}{ax^2+bx+c} dx"
    if "\\frac{1}{a^2+x^2}" in f:
        return "Tính tích phân \\int \\frac{1}{a^2+x^2} dx = \\frac{1}{a}\\arctan\\frac{x}{a}"
    if "\\frac{1}{x}" in f:
        return "Tính tích phân \\int \\frac{1}{x} dx = \\ln|x|"
    if "\\frac{1}{\\sqrt{a-x}}" in f or "\\frac{1}{\\sqrt{a^2" in f or "\\frac{1}{\\sqrt{x" in f:
        return "Tính tích phân phân thức chứa căn bậc hai"
    if "\\frac{x^2}{a^2" in f:
        return "Tính tích phân \\int \\frac{x^2}{a^2+x^2} dx"
    if "\\frac{x^3}{a^2" in f:
        return "Tính tích phân \\int \\frac{x^3}{a^2+x^2} dx"
    if "\\frac{x}{(x+a)^2}" in f:
        return "Tính tích phân \\int \\frac{x}{(x+a)^2} dx"
    if "\\frac{x}{a^2+x^2}" in f:
        return "Tính tích phân \\int \\frac{x}{a^2+x^2} dx = \\frac{1}{2}\\ln|a^2+x^2|"
    if "\\frac{x}{\\sqrt" in f:
        return "Tính tích phân phân thức chia cho căn bậc hai"
    if "\\frac{\\ln ax}{x}" in f:
        return "Tính tích phân \\int \\frac{\\ln(ax)}{x} dx"
    if "x e^x" in f:
        return "Tính tích phân \\int x e^x dx bằng tích phân từng phần"
    if "x \\sqrt{x-a}" in f or "x\\sqrt{x-a}" in f:
        return "Tính tích phân \\int x\\sqrt{x-a} \\, dx"
    if "x \\sqrt{x^2" in f or "x\\sqrt{x^2" in f:
        return "Tính tích phân \\int x\\sqrt{x^2 \\pm a^2} \\, dx"
    if "\\frac{dx}{(a^2+x^2)^{3/2}}" in f:
        return "Tính tích phân \\int \\frac{dx}{(a^2+x^2)^{3/2}}"
    return "Tính tích phân bất định theo công thức tra bảng"


def parse_deriv_instruction(formula):
    """Tạo instruction cụ thể cho đạo hàm ngược lượng giác."""
    f = formula
    if "arccsc" in f:
        return "Tính đạo hàm của hàm arccsc(x)"
    if "arccos" in f:
        return "Tính đạo hàm của hàm arccos(x)"
    if "arccot" in f:
        return "Tính đạo hàm của hàm arccot(x)"
    if "arcsec" in f:
        return "Tính đạo hàm của hàm arcsec(x)"
    if "arcsin" in f:
        return "Tính đạo hàm của hàm arcsin(x)"
    if "arctan" in f:
        return "Tính đạo hàm của hàm arctan(x)"
    if "\\csc x" in f:
        return "Tính đạo hàm của hàm csc(x)"
    if "\\cos x" in f:
        return "Tính đạo hàm của hàm cos(x)"
    if "\\cot x" in f:
        return "Tính đạo hàm của hàm cot(x)"
    if "\\sec x" in f:
        return "Tính đạo hàm của hàm sec(x)"
    if "\\sin x" in f:
        return "Tính đạo hàm của hàm sin(x)"
    if "\\tan x" in f:
        return "Tính đạo hàm của hàm tan(x)"
    return "Tính đạo hàm của hàm lượng giác hoặc ngược lượng giác"


def parse_trig_instruction(formula):
    """Tạo instruction cụ thể cho hằng đẳng thức lượng giác."""
    f = formula
    if "\\sin^2" in f and "\\cos^2" in f and "= 1" in f:
        return "Đẳng thức Pythagorean cơ bản: sin²θ + cos²θ = 1"
    if "\\cot^2" in f and "\\csc^2" in f:
        return "Đẳng thức Pythagorean: 1 + cot²θ = csc²θ"
    if "\\tan^2" in f and "\\sec^2" in f:
        return "Đẳng thức Pythagorean: tan²θ + 1 = sec²θ"
    if "\\csc" in f and "\\frac{1}{\\sin" in f:
        return "Định nghĩa hàm csc(θ) = 1/sin(θ)"
    if "\\sec" in f and "\\frac{1}{\\cos" in f:
        return "Định nghĩa hàm sec(θ) = 1/cos(θ)"
    if "\\cot" in f and "\\frac{1}{\\tan" in f:
        return "Định nghĩa hàm cot(θ) = cos(θ)/sin(θ)"
    if "\\tan" in f and "\\frac{\\sin" in f and "\\cos" in f:
        return "Định nghĩa hàm tan(θ) = sin(θ)/cos(θ)"
    if "\\cos(\\alpha" in f and "\\pm" in f:
        return "Công thức cộng góc cho hàm cos: cos(α ± β)"
    if "\\sin(\\alpha" in f and "\\pm" in f:
        return "Công thức cộng góc cho hàm sin: sin(α ± β)"
    if "\\tan(\\alpha" in f and "\\pm" in f:
        return "Công thức cộng góc cho hàm tan: tan(α ± β)"
    if "\\tan 2" in f or "\\cot 2" in f:
        return "Công thức góc đôi (double angle formula)"
    if "\\tan 3" in f or "\\cot 3" in f:
        return "Công thức góc ba (triple angle formula)"
    return "Áp dụng công thức và hằng đẳng thức lượng giác"


LABEL_MAP_FULL = {
    "integral": "calculus",
    "trigonometry": "trigonometry",
    "fraction": "algebra",
    "exponential": "algebra",
    "root": "algebra",
    "equation": "algebra",
    "geometry": "geometry",
    "algebra": "algebra",
    "statistics": "statistics",
    "optimization": "optimization",
    "linear_algebra": "linear_algebra",
    "special_function": "mathematical_physics",
    "formula": "algebra",
}

# ===========================================================================
# HELPER FUNCTIONS
# ===========================================================================

def get_formula_type(label):
    return LABEL_MAP_FULL.get(label, "algebra")


def get_difficulty(formula, label):
    if label == "integral":
        complex_patterns = ["Gamma", "erf", "sinh", "cosh", "\\csc", "^{3/2}", "x^n e^{ax}"]
        if any(p in formula for p in complex_patterns):
            return "hard"
        return "medium"
    if label in ["trigonometry"]:
        if "alpha" in formula or "beta" in formula or "3\\theta" in formula:
            return "medium"
        return "easy"
    if label == "root":
        if "arcsec" in formula or "arccsc" in formula:
            return "medium"
        return "easy"
    if label in ["linear_algebra", "optimization", "statistics"]:
        return "medium"
    if label == "special_function":
        return "hard"
    return "easy"


def extract_tags(formula, label):
    tags = []
    if label == "integral":
        tags.extend(["integral", "calculus"])
        if "\\sin" in formula or "\\cos" in formula or "\\tan" in formula:
            tags.append("trigonometric_integral")
        if "e^" in formula:
            tags.append("exponential_integral")
        if "\\ln" in formula or "\\log" in formula:
            tags.append("logarithmic_integral")
        if "\\sqrt" in formula:
            tags.append("radical_integral")
        if "\\frac" in formula:
            tags.append("rational_integral")
        if "u dv" in formula:
            tags.append("integration_by_parts")
        if "sinh" in formula or "cosh" in formula or "tanh" in formula:
            tags.append("hyperbolic")
    elif label == "trigonometry":
        tags.extend(["trigonometry", "identity"])
        if "\\sin" in formula: tags.append("sine")
        if "\\cos" in formula: tags.append("cosine")
        if "\\tan" in formula: tags.append("tangent")
        if "\\cot" in formula: tags.append("cotangent")
        if "\\sec" in formula: tags.append("secant")
        if "\\csc" in formula: tags.append("cosecant")
        if "\\alpha" in formula and "\\beta" in formula: tags.append("angle_addition")
        if "2\\theta" in formula: tags.append("double_angle")
        if "3\\theta" in formula: tags.append("triple_angle")
    elif label == "root":
        tags.extend(["calculus", "derivative"])
        if "arc" in formula: tags.append("inverse_trigonometry")
        if "\\sqrt" in formula: tags.append("radical")
    elif label == "linear_algebra":
        tags.extend(["linear_algebra", "matrix", "gradient"])
    elif label == "optimization":
        tags.extend(["optimization", "gradient", "machine_learning"])
        if "softmax" in formula: tags.append("softmax")
        if "sigmoid" in formula or "\\sigma" in formula: tags.append("sigmoid")
        if "tanh" in formula: tags.append("tanh")
        if "ReLU" in formula or "relu" in formula.lower(): tags.append("relu")
        if "\\lambda" in formula: tags.append("regularization")
    elif label == "statistics":
        tags.extend(["statistics", "probability"])
    elif label in ["exponential", "fraction", "algebra"]:
        tags.extend(["algebra"])
        if "\\frac" in formula: tags.append("fraction")
        if "^" in formula: tags.append("exponent")
        if "\\sum" in formula: tags.append("series")
        if "e^" in formula: tags.append("exponential")
        if "S_1" in formula or "\\bigcap" in formula or "\\bigcup" in formula or "\\subset" in formula:
            tags.extend(["set_theory"])
    elif label == "geometry":
        tags.extend(["set_theory", "geometry"])
    elif label == "special_function":
        tags.extend(["special_function", "mathematical_physics"])
    else:
        tags.append(label)
    tags.append("standard_variables")
    return list(dict.fromkeys(tags))


def _slug(text):
    """Chuyển text thành lowercase_underscore slug."""
    text = text.lower()
    text = re.sub(r'[àáảãạăắặẳẵặâấầẩẫậ]', 'a', text)
    text = re.sub(r'[èéẻẽẹêếềểễệ]', 'e', text)
    text = re.sub(r'[ìíỉĩị]', 'i', text)
    text = re.sub(r'[òóỏõọôốồổỗộơớờởỡợ]', 'o', text)
    text = re.sub(r'[ùúủũụưứừửữự]', 'u', text)
    text = re.sub(r'[ýỳỷỹỵ]', 'y', text)
    text = re.sub(r'[đ]', 'd', text)
    text = re.sub(r'[^a-z0-9_]', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')


def _extract_content_slug(formula, label, description):
    """Tạo slug mô tả nội dung từ formula + label."""
    f = formula

    # ── INTEGRAL ──────────────────────────────────────────────
    if label == "integral":
        if "u dv" in f or "u dv = uv" in f:
            return "integration_by_parts"
        if "\\int_{-\\infty}^{\\infty}" in f or "\\int _{-" in f:
            return "definite_integral_real_line"
        if "e^{-ax^2}" in f or "e^{ax^2}" in f or "e^{-x^2}" in f:
            return "gaussian_integral"
        if "e^{bx}" in f and "\\cos ax" in f:
            return "integral_exp_bx_cos_ax"
        if "e^{bx}" in f and "\\sin ax" in f:
            return "integral_exp_bx_sin_ax"
        if "e^x" in f and "\\cos x" in f and "\\sin x" in f:
            return "integral_ex_cos_x"
        if "e^x" in f and "\\sin x" in f:
            return "integral_ex_sin_x"
        if "x e^x" in f and "\\cos" not in f and "\\sin" not in f:
            return "integral_x_ex"
        if "x^3" in f and "e^{x}" in f:
            return "integral_x3_ex"
        if "x^2" in f and "e^{ax}" in f:
            return "integral_x2_eax"
        if "x^2" in f and "e^{x}" in f:
            return "integral_x2_ex"
        if "x^n" in f and "e^{ax}" in f and "Gamma" in f:
            return "integral_xn_eax_gamma"
        if "x^n" in f and "e^{ax}" in f:
            return "integral_xn_eax_reduction"
        if "x e^{ax}" in f:
            return "integral_x_eax"
        if "x e^{-ax^2}" in f:
            return "integral_x_exp_neg_ax2"
        if "e^{ax}" in f:
            return "integral_eax"
        if "\\tanh" in f:
            return "integral_tanh_ax"
        if "\\sinh" in f and "\\cosh" in f:
            return "integral_sinh_cosh_ax"
        if "\\cosh" in f:
            return "integral_cosh_ax"
        if "\\sinh" in f:
            return "integral_sinh_ax"
        if "\\ln ( x^2 + a^2" in f or "ln ( x^2 + a^2" in f:
            return "integral_ln_x2_plus_a2"
        if "\\ln ( x^2 - a^2" in f or "ln ( x^2 - a^2" in f:
            return "integral_ln_x2_minus_a2"
        if "\\ln ax" in f and "\\frac" not in f:
            return "integral_ln_ax"
        if "\\ln (ax + b)" in f:
            return "integral_ln_ax_plus_b"
        if "\\frac{\\ln ax}{x}" in f:
            return "integral_ln_ax_over_x"
        if "\\Gamma" in f:
            return "integral_gamma_function"
        if "\\csc^3" in f:
            return "integral_csc3_x"
        if "\\csc^n" in f:
            return "integral_cscn_cot_x"
        if "\\csc^2" in f:
            return "integral_csc2_ax"
        if "\\csc x" in f and "\\sec x" in f:
            return "integral_sec_csc_x"
        if "\\csc x" in f:
            return "integral_csc_x"
        if "\\sec x" in f and "\\tan x" in f and "\\sec^" not in f:
            return "integral_sec_tan_x"
        if "\\sec^3" in f:
            return "integral_sec3_x"
        if "\\sec^2" in f and "\\tan x" in f:
            return "integral_sec2_tan_x"
        if "\\sec^n" in f:
            return "integral_secn_tan_x"
        if "\\sec^2" in f:
            return "integral_sec2_ax"
        if "\\tan^3" in f:
            return "integral_tan3_ax"
        if "\\tan^2" in f:
            return "integral_tan2_ax"
        if "\\tan ax" in f or "\\tan x" in f:
            return "integral_tan_ax"
        if "x e^x" in f and "\\cos" in f:
            return "integral_xex_cos_x"
        if "x e^x" in f and "\\sin" in f:
            return "integral_xex_sin_x"
        if "x^2" in f and "\\cos ax" in f:
            return "integral_x2_cos_ax"
        if "x^2" in f and "\\cos x" in f:
            return "integral_x2_cos_x"
        if "x^2" in f and "\\sin ax" in f:
            return "integral_x2_sin_ax"
        if "x^2" in f and "\\sin x" in f:
            return "integral_x2_sin_x"
        if "x \\cos ax" in f or "x\\cos ax" in f:
            return "integral_x_cos_ax"
        if "x \\cos x" in f:
            return "integral_x_cos_x"
        if "x \\sin ax" in f or "x\\sin ax" in f:
            return "integral_x_sin_ax"
        if "x \\sin x" in f:
            return "integral_x_sin_x"
        if "\\sin^2 ax" in f and "\\cos^2 ax" in f:
            return "integral_sin2_cos2_ax"
        if "\\sin^2 x" in f and "\\cos x" in f:
            return "integral_sin2_cos_x"
        if "\\cos^2 ax" in f and "\\sin ax" in f:
            return "integral_cos2_sin_ax"
        if "\\sin^3" in f:
            return "integral_sin3_ax"
        if "\\cos^3" in f:
            return "integral_cos3_ax"
        if "\\sin^2" in f:
            return "integral_sin2_ax"
        if "\\cos^2" in f:
            return "integral_cos2_ax"
        if "\\sin ax" in f or "\\sin x" in f:
            return "integral_sin_ax"
        if "\\cos ax" in f or "\\cos x" in f:
            return "integral_cos_ax"
        if "(ax+b)^{3/2}" in f:
            return "integral_ax_plus_b_3_2"
        if "(ax+b)" in f and "\\sqrt" in f:
            return "integral_sqrt_ax_plus_b"
        if "x(x+a)^n" in f:
            return "integral_x_times_x_plus_a_n"
        if "(x+a)^n" in f:
            return "integral_x_plus_a_n"
        if "\\frac{1}{(x+a)(x+b)}" in f:
            return "integral_partial_fractions_two_roots"
        if "\\frac{1}{(x+a)^2}" in f:
            return "integral_one_over_x_plus_a_sq"
        if "\\frac{x}{(x+a)^2}" in f:
            return "integral_x_over_x_plus_a_sq"
        if "\\frac{1}{1+x^2}" in f:
            return "integral_one_over_1_plus_x2_arctan"
        if "\\frac{1}{ax+b}" in f:
            return "integral_one_over_ax_plus_b"
        if "\\frac{1}{ax^2+bx+c}" in f:
            return "integral_one_over_quadratic"
        if "\\frac{1}{a^2+x^2}" in f:
            return "integral_one_over_a2_plus_x2"
        if "\\frac{x^3}{a^2+x^2}" in f:
            return "integral_x3_over_a2_plus_x2"
        if "\\frac{x^2}{a^2+x^2}" in f:
            return "integral_x2_over_a2_plus_x2"
        if "\\frac{x}{a^2+x^2}" in f:
            return "integral_x_over_a2_plus_x2"
        if "\\frac{1}{x}" in f and "\\sqrt" not in f:
            return "integral_one_over_x_ln"
        if "\\frac{1}{\\sqrt{a-x}}" in f:
            return "integral_one_over_sqrt_a_minus_x"
        if "\\frac{1}{\\sqrt{a^2 - x^2}}" in f:
            return "integral_one_over_sqrt_a2_minus_x2"
        if "\\frac{1}{\\sqrt{x\\pm a}}" in f or "\\frac{1}{\\sqrt{x+" in f:
            return "integral_one_over_sqrt_x_pm_a"
        if "\\frac{1}{\\sqrt{x^2 \\pm a^2}}" in f:
            return "integral_one_over_sqrt_x2_pm_a2"
        if "\\frac{x}{\\sqrt{a^2-x^2}}" in f:
            return "integral_x_over_sqrt_a2_minus_x2"
        if "\\frac{x}{\\sqrt{x\\pm a}}" in f:
            return "integral_x_over_sqrt_x_pm_a"
        if "\\frac{x}{\\sqrt{x^2\\pm a^2}}" in f:
            return "integral_x_over_sqrt_x2_pm_a2"
        if "\\frac{dx}{(a^2+x^2)^{3/2}}" in f:
            return "integral_dx_over_a2_plus_x2_3_2"
        if "x \\sqrt{x^2" in f or "x\\sqrt{x^2" in f:
            return "integral_x_sqrt_x2_pm_a2"
        if "x \\sqrt{x-a}" in f or "x\\sqrt{x-a}" in f:
            return "integral_x_sqrt_x_minus_a"
        if "\\sqrt{x-a}" in f:
            return "integral_sqrt_x_minus_a"
        if "x^2" in f and "e^{-ax^2}" in f:
            return "integral_x2_exp_neg_ax2"
        if "x^n" in f:
            return "integral_power_xn"
        return "integral_standard_formula"

    # ── ROOT (đạo hàm ngược lượng giác / lượng giác thường) ──
    if label == "root":
        if "arccsc" in f:  return "calc_deriv_arccsc"
        if "arccos" in f:  return "calc_deriv_arccos"
        if "arccot" in f:  return "calc_deriv_arccot"
        if "arcsec" in f:  return "calc_deriv_arcsec"
        if "arcsin" in f:  return "calc_deriv_arcsin"
        if "arctan" in f:  return "calc_deriv_arctan"
        if "\\csc x" in f: return "calc_deriv_csc"
        if "\\cos x" in f: return "calc_deriv_cos"
        if "\\cot x" in f: return "calc_deriv_cot"
        if "\\sec x" in f: return "calc_deriv_sec"
        if "\\sin x" in f: return "calc_deriv_sin"
        if "\\tan x" in f: return "calc_deriv_tan"
        return "calc_deriv_trig"

    # ── TRIGONOMETRY ──────────────────────────────────────────
    if label == "trigonometry":
        if "\\sin^2" in f and "\\cos^2" in f and "= 1" in f:
            return "trig_pythagorean_identity_sin_cos"
        if "\\cot^2" in f and "\\csc^2" in f:
            return "trig_pythagorean_identity_cot_csc"
        if "\\tan^2" in f and "\\sec^2" in f:
            return "trig_pythagorean_identity_tan_sec"
        if "\\csc" in f and "\\frac{1}{\\sin" in f:
            return "trig_definition_csc"
        if "\\sec" in f and "\\frac{1}{\\cos" in f:
            return "trig_definition_sec"
        if "\\cot" in f and "\\frac{1}{\\tan" in f:
            return "trig_definition_cot"
        if "\\tan" in f and "\\frac{\\sin" in f:
            return "trig_definition_tan"
        if "\\cos(\\alpha" in f and "\\pm" in f:
            return "trig_angle_addition_cos"
        if "\\sin(\\alpha" in f and "\\pm" in f:
            return "trig_angle_addition_sin"
        if "\\tan(\\alpha" in f and "\\pm" in f:
            return "trig_angle_addition_tan"
        if "\\tan 2\\theta" in f:
            return "trig_double_angle_tan"
        if "\\cot 2\\theta" in f:
            return "trig_double_angle_cot"
        if "\\tan 3\\theta" in f:
            return "trig_triple_angle_tan"
        if "\\cot 3\\theta" in f:
            return "trig_triple_angle_cot"
        if "\\int" in f and "\\sin^2" in f:
            return "integral_sin2_ax"
        if "\\int" in f and "\\cos^2" in f:
            return "integral_cos2_ax"
        return "trig_identity"

    # ── LINEAR ALGEBRA ────────────────────────────────────────
    if label == "linear_algebra":
        if "x^T A x" in f:         return "linalg_gradient_quadratic_form"
        if "\\|Ax - b\\|" in f:    return "linalg_gradient_mse_matrix"
        if "\\|x\\|^2 - \\|y\\|^2" in f: return "linalg_diff_norm_sq"
        if "\\|x\\|^2" in f and "(x - y)^T" in f: return "linalg_norm_diff_inner_product"
        if "x^T A y" in f:         return "linalg_gradient_bilinear_x"
        if "y^T A x" in f:         return "linalg_gradient_bilinear_y"
        if "\\|x\\|" in f and "\\frac{x}{" in f: return "linalg_gradient_norm_l2"
        if "x_i - y_i)(x_i + y_i" in f: return "linalg_diff_sum_squares"
        if "\\|x\\|_1 - \\|y\\|_1" in f: return "linalg_norm_l1_triangle"
        if "(x^T x)" in f or "x_i^T" in f: return "linalg_partial_deriv_norm"
        if "\\frac{\\partial}{\\partial x_i}" in f and "\\sum_j" in f: return "linalg_partial_deriv_sum"
        return "linalg_matrix_identity"

    # ── OPTIMIZATION ──────────────────────────────────────────
    if label == "optimization":
        if "softmax" in f:          return "opt_gradient_log_sum_exp_softmax"
        if "\\sigma" in f and "(1 - \\sigma" in f: return "opt_gradient_sigmoid"
        if "tanh" in f and "1 - tanh^2" in f: return "opt_gradient_tanh"
        if "max(0" in f or "ReLU" in f: return "opt_gradient_relu"
        if "\\hat{y}" in f and "\\log" in f: return "opt_gradient_cross_entropy"
        if "\\|Ax - b\\|" in f:    return "opt_gradient_mse"
        if "x^T A x" in f:         return "opt_gradient_quadratic"
        if "\\lambda" in f and "\\|x\\|^2" in f: return "opt_gradient_l2_regularization"
        if "|x_i|" in f or "sign" in f: return "opt_gradient_l1_lasso"
        if "\\log p(x)" in f:      return "opt_gradient_log_likelihood"
        if "\\log(1 + e^x)" in f:  return "opt_gradient_softplus"
        if "\\log \\sum" in f:     return "opt_gradient_log_sum_exp"
        if "\\nabla \\log x" in f: return "opt_gradient_log"
        if "\\nabla e^x" in f:     return "opt_gradient_exp"
        if "\\nabla \\|x\\|" in f: return "opt_gradient_norm"
        return "opt_gradient_rule"

    # ── STATISTICS ────────────────────────────────────────────
    if label == "statistics":
        if "\\mu)(y_i" in f or "\\mu\\nu" in f: return "stat_covariance_short_form"
        if "n\\mu = 0" in f or "\\sum x_i - n" in f: return "stat_mean_deviation_zero"
        if "\\approx" in f and "f'(a)(x - a)" in f: return "stat_linearization"
        if "2h f'(x)" in f:        return "stat_finite_difference_central"
        if "h^2 f''(x)" in f:      return "stat_finite_difference_second_order"
        if "x_i^2 - \\sum y_i^2" in f: return "stat_diff_sum_squares"
        if "(x_i - y_i)(x_i + y_i" in f: return "stat_diff_identity"
        if "\\|x\\|_1 - \\|y\\|_1" in f: return "stat_norm_l1_bound"
        if "\\|x\\|^2 - \\|y\\|^2" in f and "(x - y)^T" in f: return "stat_norm_diff_bilinear"
        if "\\sum x_i y_i - n\\mu\\nu" in f: return "stat_covariance_expanded"
        if "\\sum x_i - n\\mu" in f: return "stat_sum_minus_n_mean"
        return "stat_formula"

    # ── GEOMETRY / SET THEORY ─────────────────────────────────
    if label == "geometry":
        if "S^c" in f:             return "set_complement"
        if "\\bigcap" in f:        return "set_intersection_n"
        if "\\bigcup" in f:        return "set_union_n"
        if "\\subset" in f or "\\supset" in f: return "set_subset_relation"
        if "= T" in f:             return "set_equality"
        if "x_n" in f:             return "set_finite_listing"
        if "x_1, x_2" in f:       return "set_countable_listing"
        return "set_theory_notation"

    # ── SPECIAL FUNCTION ──────────────────────────────────────
    if label == "special_function":
        if "\\cos(\\alpha" in f:   return "trig_angle_addition_cos"
        if "\\sin(\\alpha" in f:   return "trig_angle_addition_sin"
        if "\\tan(\\alpha" in f:   return "trig_angle_addition_tan"
        if "z = r(" in f:          return "complex_polar_form"
        if "e^{i" in f and "\\pi" in f: return "complex_euler_identity"
        return "special_function_formula"

    # ── EXPONENTIAL / FRACTION / ALGEBRA / FORMULA ───────────
    # Trích từ description nếu có nội dung tiếng Anh hoặc dễ đọc
    desc_clean = description.strip()
    for prefix in [
        "Hiệu hai tổng bình phương", "Bất đẳng thức norm L1",
        "Hiệu norm bình phương", "Linearization",
        "Sai phân trung tâm", "Sai phân bậc hai",
        "Tổng quanh mean", "Covariance dạng rút gọn",
        "Gradient dạng quadratic form", "Gradient MSE dạng ma trận",
        "Đạo hàm log", "Đạo hàm exponential", "Gradient softplus",
        "Gradient ReLU", "Đạo hàm tổng", "Đạo hàm từng phần norm",
        "Gradient log-sum-exp", "Gradient cross-entropy",
        "Gradient norm L2", "Regularization L2", "Gradient L1",
        "Gradient theo x", "Gradient theo x (transpose)",
        "Gradient sigmoid", "Gradient tanh", "Log-derivative trick",
        "Hiệu hai tổng", "Biến đổi tổng", "Hiệu log",
        "Chuẩn hóa log", "Biến đổi exponential",
    ]:
        if desc_clean == prefix or desc_clean.startswith(prefix + ":"):
            slug = _slug(prefix)
            prefix_map2 = {
                "exponential": "alg_exp",
                "fraction": "alg",
                "algebra": "alg",
                "formula": "formula",
                "optimization": "opt",
                "linear_algebra": "linalg",
                "statistics": "stat",
            }
            p = prefix_map2.get(label, "alg")
            return f"{p}_{slug}"

    # Formula-based slug từ content LaTeX
    if "H_{n}(" in f or "H_n(" in f:
        if "(-1)^{n}e^{x^{2}}" in f: return "special_hermite_rodrigues_formula"
        if "\\sum" in f and "n!" in f: return "special_hermite_series_expansion"
        if "\\frac{d^{n}}{dx^{n}}" in f: return "special_hermite_operator_form"
        if "(2n)!" in f: return "special_hermite_even_at_zero"
        if "H_{2n+1}(0)" in f: return "special_hermite_odd_at_zero"
    if "e^{2xt-t^{2}}" in f: return "special_hermite_generating_function"
    if "\\Psi_n" in f: return "special_hermite_quantum_eigenfunction"
    if "\\frac{\\mathrm{d}^2y" in f and "2ny" in f: return "special_hermite_ode"
    if "\\frac{\\mathrm{d}^2y" in f and "\\lambda" in f: return "special_harmonic_oscillator_ode"
    if "\\frac{\\mathrm{d}^2y" in f and "\\frac{\\mathrm{d}y" in f:
        return "special_ode_second_order"
    if "e^{2xt" in f: return "special_generating_function"
    if "\\exp{" in f and "\\frac{\\mathrm{d}^2}" in f: return "special_exp_deriv_operator"
    if "i = \\sqrt{-1}" in f: return "complex_imaginary_unit_definition"
    if "z = r(" in f: return "complex_polar_form"
    if "e^{i" in f: return "complex_euler_form"
    if "S^c" in f: return "set_complement"
    if "\\bigcap" in f: return "set_intersection_n"
    if "\\bigcup" in f: return "set_union_n"
    if "\\subset" in f: return "set_subset"
    if "= T" in f and "S" in f: return "set_equality"

    # Fallback theo label
    prefix_map3 = {
        "exponential": "alg_exp",
        "fraction": "alg",
        "algebra": "alg",
        "formula": "alg",
        "equation": "alg_eq",
    }
    p = prefix_map3.get(label, "alg")
    short = hashlib.md5(formula.encode()).hexdigest()[:8]
    return f"{p}_{short}"


def make_id(formula, label, index, description=""):
    """Tạo ID mô tả nội dung rõ ràng, giống phong cách alg_fraction_subtract_same_denominator."""
    prefix_map = {
        "integral": "calc",
        "trigonometry": "trig",
        "fraction": "alg",
        "exponential": "alg",
        "root": "calc",
        "equation": "alg",
        "geometry": "set",
        "algebra": "alg",
        "statistics": "stat",
        "optimization": "opt",
        "linear_algebra": "linalg",
        "special_function": "special",
        "formula": "alg",
    }
    slug = _extract_content_slug(formula, label, description)
    return slug


def get_instruction(formula, label, description):
    """Tạo instruction cụ thể theo label."""
    if label == "integral":
        return parse_integral_instruction(formula)
    elif label == "root":
        return parse_deriv_instruction(formula)
    elif label == "trigonometry" or label == "special_function":
        if "\\int" in formula:
            return parse_integral_instruction(formula)
        return parse_trig_instruction(formula)
    else:
        # Generic approach: clean description
        desc = description.strip()
        prefixes_to_remove = [
            "Công thức phân thức:", "Công thức tích phân:",
            "Công thức lượng giác:", "Công thức căn thức:",
            "Công thức mũ - lũy thừa - đa thức",
            "Công thức mũ - phân thức - lũy thừa - đa thức",
            "Công thức lũy thừa:", "Hàm đặc biệt:",
            "Công thức hình học:", "Công thức:", "Đẳng thức:",
            "Tích phân từng phần", "Tích phân ln|x|",
            "Công thức mũ - lũy thừa",
            "Hiệu hai tổng bình phương", "Bất đẳng thức norm L1",
            "Hiệu norm bình phương", "Linearization",
            "Sai phân trung tâm", "Sai phân bậc hai",
            "Tổng quanh mean", "Covariance dạng rút gọn",
            "Gradient dạng quadratic form", "Gradient MSE dạng ma trận",
            "Đạo hàm log", "Đạo hàm exponential", "Gradient softplus",
            "Gradient ReLU", "Đạo hàm tổng", "Đạo hàm từng phần norm",
            "Gradient log-sum-exp", "Gradient cross-entropy",
            "Gradient norm L2", "Regularization L2", "Gradient L1",
            "Gradient theo x", "Gradient theo x (transpose)",
            "Gradient sigmoid", "Gradient tanh", "Log-derivative trick",
        ]
        for p in prefixes_to_remove:
            if desc.startswith(p) or desc == p:
                desc = desc[len(p):].strip()
                break
        if len(desc) > 5 and not desc.startswith("\\") and "=" not in desc and "\\" not in desc:
            return desc[:120]
        # Fallback: label-based
        label_fallback = {
            "fraction": "Rút gọn hoặc tính biểu thức đại số",
            "exponential": "Tính biểu thức lũy thừa hoặc tập hợp",
            "equation": "Giải hoặc phân tích phương trình đại số",
            "geometry": "Áp dụng phép toán và ký hiệu tập hợp",
            "algebra": "Rút gọn biểu thức đại số",
            "statistics": "Tính đại lượng thống kê",
            "optimization": "Tính gradient hoặc áp dụng quy tắc tối ưu",
            "linear_algebra": "Tính gradient trong đại số tuyến tính",
        }
        # Detect content for better fallback
        if label == "optimization" or "\\nabla" in formula:
            if "softmax" in formula: return "Tính gradient của hàm log-sum-exp (gradient softmax)"
            if "sigmoid" in formula or "\\sigma" in formula: return "Tính gradient của hàm sigmoid σ(x)"
            if "tanh" in formula: return "Tính gradient của hàm tanh(x)"
            if "relu" in formula.lower() or "max(0" in formula: return "Tính gradient của hàm ReLU"
            if "cross-entropy" in desc.lower() or "\\hat{y}" in formula: return "Tính gradient của hàm cross-entropy"
            if "MSE" in desc or "\\|Ax - b\\|" in formula or "Ax - b" in formula: return "Tính gradient của hàm mất mát MSE (bình phương sai số)"
            if "quadratic" in desc.lower() or "x^T A x" in formula: return "Tính gradient của dạng toàn phương x^T A x"
            if "\\lambda" in formula and "\\|x\\|" in formula: return "Tính gradient với regularization L2 (Ridge)"
            if "\\|x\\|_1" in formula or "sign" in formula or "|x_i|" in formula: return "Tính gradient của chuẩn L1 (Lasso)"
            if "\\log p(x)" in formula: return "Tính gradient log-likelihood (log-derivative trick)"
            return label_fallback.get(label, "Áp dụng công thức toán học")
        if label == "linear_algebra" or "\\nabla" in formula or "^T" in formula:
            if "\\|x\\|^2 - \\|y\\|^2" in formula: return "Tính hiệu bình phương của các norm"
            if "x^T A" in formula or "A y" in formula: return "Tính gradient biểu thức tuyến tính x^T A y"
            if "\\|x\\|^2" in formula and "= (x - y)^T" in formula: return "Tính hiệu bình phương norm theo dạng tích vô hướng"
            if "x_i^2 - \\sum y_i^2" in formula or "x_i - y_i" in formula: return "Đẳng thức hiệu tổng bình phương"
            if "(x^T x)" in formula or "x_i^T" in formula: return "Tính đạo hàm riêng của biểu thức norm"
        if label == "statistics":
            if "\\mu\\nu" in formula or "\\mu)(y_i" in formula: return "Tính covariance (hiệp phương sai) dưới dạng rút gọn"
            if "n\\mu = 0" in formula or "\\sum x_i - n" in formula: return "Tính tổng sai lệch so với trung bình (luôn bằng 0)"
            if "\\approx" in formula and "f'(" in formula: return "Xấp xỉ tuyến tính (linearization) của hàm số"
            if "2h f'(x)" in formula: return "Công thức sai phân trung tâm để tính đạo hàm"
            if "h^2 f''(x)" in formula: return "Công thức sai phân bậc hai để ước lượng đạo hàm bậc hai"
        return label_fallback.get(label, "Áp dụng công thức toán học")


def get_instruction_variants(instruction, label):
    """Tạo 3 variants của instruction."""
    vmap = {
        "integral": [
            "Tính tích phân theo công thức tra bảng",
            "Áp dụng công thức tích phân nguyên mẫu",
            "Evaluate the integral using standard formula",
        ],
        "trigonometry": [
            "Sử dụng hằng đẳng thức lượng giác",
            "Chứng minh hoặc áp dụng công thức lượng giác",
            "Apply trigonometric identity",
        ],
        "root": [
            "Tính đạo hàm hàm lượng giác ngược theo biến x",
            "Áp dụng quy tắc đạo hàm hàm ngược",
            "Differentiate the inverse trigonometric function",
        ],
        "linear_algebra": [
            "Áp dụng quy tắc gradient ma trận",
            "Tính gradient theo biến vector",
            "Apply matrix gradient rule",
        ],
        "optimization": [
            "Tính gradient hàm mục tiêu trong bài toán tối ưu",
            "Áp dụng vi phân vi giải cho học máy",
            "Compute gradient for optimization algorithm",
        ],
        "statistics": [
            "Tính đặc trưng thống kê của mẫu dữ liệu",
            "Áp dụng công thức thống kê mô tả",
            "Apply statistical formula to data",
        ],
        "geometry": [
            "Áp dụng phép toán tập hợp",
            "Xác định quan hệ giữa các tập hợp",
            "Apply set-theoretic operation",
        ],
    }
    defaults = [
        instruction,
        "Tính toán theo công thức cho trước",
        "Apply the given mathematical formula",
    ]
    variants = vmap.get(label, defaults)
    return variants


def get_steps(formula, label):
    """Tạo steps chi tiết theo label."""
    if label == "integral":
        if "u dv" in formula:
            return [
                "Chọn u và dv từ biểu thức tích phân theo quy tắc LIATE",
                "Tính đạo hàm du và nguyên hàm v",
                "Áp dụng công thức: ∫u dv = uv - ∫v du",
                "Tính tích phân ∫v du còn lại",
                "Tổng hợp kết quả và thêm hằng số C"
            ]
        return [
            "Nhận dạng dạng của tích phân: biểu thức, hệ số, biến tích phân",
            "Đối chiếu với bảng công thức tích phân nguyên mẫu",
            "Áp dụng công thức phù hợp (đổi biến hoặc tích phân từng phần nếu cần)",
            "Viết kết quả, thêm hằng số tích phân C cho tích phân bất định",
            "Kiểm tra kết quả bằng cách lấy đạo hàm của vế phải"
        ]
    elif label == "trigonometry":
        return [
            "Xác định các hàm lượng giác xuất hiện trong công thức",
            "Nhận diện loại hằng đẳng thức (Pythagorean, cộng góc, góc đôi, ...)",
            "Áp dụng định nghĩa hoặc chứng minh từ tam giác vuông/đường tròn đơn vị",
            "Rút gọn hoặc biến đổi biểu thức về dạng chuẩn"
        ]
    elif label == "root":
        return [
            "Xác định hàm lượng giác ngược cần tính đạo hàm",
            "Đặt y = f(x) và áp dụng quy tắc đạo hàm hàm ngược: f'(x) = 1/g'(f(x))",
            "Rút gọn biểu thức đạo hàm về dạng chứa căn thức",
            "Xác định miền xác định của hàm (domain constraints)",
            "Viết kết quả đạo hàm theo biến x"
        ]
    elif label == "linear_algebra":
        return [
            "Xác định ma trận A, vector x, y trong biểu thức",
            "Áp dụng quy tắc gradient theo đại số ma trận",
            "Lưu ý thứ tự nhân ma trận (A·x ≠ x·A nói chung)",
            "Kiểm tra chiều (dimension) của vector gradient kết quả"
        ]
    elif label == "optimization":
        return [
            "Xác định hàm mục tiêu (hàm mất mát) cần tối ưu",
            "Tính gradient - vector đạo hàm riêng theo từng tham số",
            "Áp dụng gradient trong thuật toán cập nhật tham số",
            "Kiểm tra điều kiện hội tụ (gradient = 0 tại điểm cực trị)"
        ]
    elif label == "statistics":
        return [
            "Thu thập bộ dữ liệu mẫu {x_1, x_2, ..., x_n}",
            "Xác định đại lượng thống kê cần tính (trung bình, phương sai, ...)",
            "Áp dụng công thức thống kê tương ứng",
            "Diễn giải kết quả: ý nghĩa về phân phối và độ phân tán của dữ liệu"
        ]
    elif label == "geometry":
        return [
            "Xác định không gian mẫu Ω và các tập hợp liên quan",
            "Áp dụng định nghĩa phép toán: giao (∩), hợp (∪), bù (S^c), con (⊂)",
            "Xác định phần tử thuộc hay không thuộc tập kết quả",
            "Biểu diễn tập kết quả theo ký hiệu chuẩn toán học"
        ]
    else:
        return [
            "Xác định các biến và tham số trong công thức",
            "Thay các giá trị đã biết vào công thức",
            "Thực hiện phép tính theo thứ tự ưu tiên (mũ → nhân/chia → cộng/trừ)",
            "Rút gọn và viết kết quả ở dạng chuẩn"
        ]


def get_reasoning(formula, label, instruction):
    """Tạo reasoning giải thích tại sao công thức đúng."""
    if label == "integral":
        if "u dv" in formula:
            return (
                "Công thức tích phân từng phần ∫u dv = uv - ∫v du là hệ quả của quy tắc tích (Leibniz). "
                "Lấy đạo hàm của uv: d(uv) = u dv + v du, suy ra u dv = d(uv) - v du, "
                "lấy tích phân hai vế ta được công thức. Đây là kỹ thuật thiết yếu khi tích phân "
                "là tích của hai loại hàm khác nhau."
            )
        if "e^{ax}" in formula or "e^{bx}" in formula or "e^x" in formula:
            return (
                "Hàm mũ e^{ax} có tính chất đặc biệt là đạo hàm bậc bất kỳ cũng là hàm mũ. "
                "Nguyên hàm của e^{ax} là (1/a)e^{ax}, kiểm chứng bằng cách lấy đạo hàm vế phải. "
                "Khi kết hợp với sin/cos, cần dùng tích phân từng phần hai lần để thu được hệ phương trình "
                "giải được cho tích phân cần tìm."
            )
        if "\\sin" in formula or "\\cos" in formula:
            return (
                "Công thức tích phân lượng giác này được chứng minh bằng cách lấy đạo hàm của vế phải. "
                "Các hệ số xuất hiện do quy tắc dây chuyền khi đạo hàm sin/cos có thêm yếu tố 'a'. "
                "Công thức hạ bậc (sin²ax = (1-cos2ax)/2) được dùng để tích phân lũy thừa của sin/cos."
            )
        if "\\ln" in formula or "\\log" in formula:
            return (
                "Nguyên hàm của ln(x) được tính bằng tích phân từng phần với u = ln(x), dv = dx. "
                "Kết quả ∫ln(x)dx = x·ln(x) - x vì d/dx(x·ln(x) - x) = ln(x) + 1 - 1 = ln(x). "
                "Các dạng phức tạp hơn như ln(ax+b) được xử lý tương tự."
            )
        return (
            "Công thức tích phân này là kết quả chuẩn trong giải tích, được chứng minh bằng cách "
            "lấy đạo hàm của vế phải và xác nhận bằng vế trái. "
            "Đây là công thức tra bảng quan trọng trong vật lý, kỹ thuật và toán ứng dụng."
        )
    elif label == "trigonometry":
        if "\\sin^2" in formula and "\\cos^2" in formula and "= 1" in formula:
            return (
                "Đây là hằng đẳng thức Pythagorean cơ bản nhất trong lượng giác. "
                "Trên đường tròn đơn vị bán kính 1, điểm P(cos θ, sin θ) luôn thỏa cos²θ + sin²θ = 1 "
                "theo định lý Pythagore. Đây là nền tảng của toàn bộ lý thuyết lượng giác."
            )
        if "\\alpha" in formula and "\\beta" in formula:
            return (
                "Công thức cộng góc được suy ra từ phép quay trong hệ tọa độ. "
                "Biểu diễn góc (α+β) như hai phép quay liên tiếp và nhân ma trận quay, "
                "ta thu được công thức mở rộng sin/cos của tổng hay hiệu hai góc."
            )
        return (
            "Hằng đẳng thức lượng giác này được suy ra từ định nghĩa cơ bản các hàm lượng giác "
            "trên đường tròn đơn vị hoặc trong tam giác vuông. "
            "Các hằng đẳng thức này là công cụ nền tảng để rút gọn và biến đổi biểu thức lượng giác."
        )
    elif label == "root":
        return (
            "Đạo hàm hàm lượng giác ngược được suy ra từ quy tắc đạo hàm hàm ngược: "
            "nếu y = arcf(x) thì f(y) = x, lấy đạo hàm hai vế: f'(y)·y' = 1, "
            "suy ra y' = 1/f'(y) = 1/f'(arcf(x)). "
            "Việc rút gọn f'(arcf(x)) dùng đến đẳng thức lượng giác Pythagorean."
        )
    elif label == "linear_algebra":
        return (
            "Gradient của biểu thức ma trận được tính theo quy tắc vi phân ma trận. "
            "Đây là nền tảng của Machine Learning: backpropagation sử dụng các công thức gradient ma trận "
            "này để cập nhật trọng số mạng nơ-ron. Trật tự nhân ma trận (transpose) là điểm dễ nhầm nhất."
        )
    elif label == "optimization":
        return (
            "Gradient là hướng tăng nhanh nhất của hàm mục tiêu. "
            "Trong gradient descent, ta cập nhật tham số theo hướng ngược gradient: θ ← θ - α∇f(θ). "
            "Công thức gradient này được suy ra bằng quy tắc vi phân tổng hợp (chain rule) "
            "áp dụng cho hàm hợp, là cốt lõi của thuật toán backpropagation."
        )
    elif label == "statistics":
        return (
            "Công thức thống kê này mô tả tính chất cơ bản của phân phối dữ liệu. "
            "Được suy ra từ định nghĩa kỳ vọng và phương sai trong lý thuyết xác suất. "
            "Dạng rút gọn của covariance rất hữu ích để tính toán hiệu quả trên tập dữ liệu lớn."
        )
    elif label == "geometry":
        return (
            "Ký hiệu và phép toán tập hợp này là nền tảng của lý thuyết tập hợp - "
            "ngôn ngữ chính thức của toán học hiện đại. "
            "Hiểu rõ sự khác biệt giữa giao (∩), hợp (∪), bù (S^c) và quan hệ bao hàm (⊂) "
            "là thiết yếu trong xác suất, logic và lý thuyết đồ thị."
        )
    else:
        return (
            f"Công thức '{instruction}' là kết quả chuẩn trong toán học. "
            "Được suy ra từ các tiên đề cơ bản và áp dụng quy tắc đại số hoặc giải tích. "
            "Kết quả này được kiểm chứng bằng cách thay vào ví dụ cụ thể hoặc lấy đạo hàm."
        )


def get_variables(formula, label):
    """Tạo variables nhất quán: x là biến chính, a là tham số."""
    variables = {}
    if label == "integral":
        variables["integration_variable"] = "x"
        if re.search(r'\ba\b', formula) or "ax" in formula or "a^2" in formula:
            variables["parameter"] = "a"
        if re.search(r'\bn\b', formula) or "n!" in formula or "^n" in formula:
            variables["order"] = "n"
        if re.search(r'\bb\b', formula) or "bx" in formula:
            variables["parameter_2"] = "b"
    elif label == "trigonometry":
        if "\\theta" in formula:
            variables["angle"] = "\\theta"
        if "\\alpha" in formula:
            variables["angle_1"] = "\\alpha"
        if "\\beta" in formula:
            variables["angle_2"] = "\\beta"
    elif label == "root":
        variables["variable"] = "x"
    elif label == "linear_algebra":
        variables["vector"] = "\\mathbf{x}"
        if "A" in formula: variables["matrix"] = "A"
        if "b" in formula: variables["vector_b"] = "\\mathbf{b}"
    elif label == "optimization":
        variables["variable"] = "x"
        if "\\lambda" in formula: variables["regularization_param"] = "\\lambda"
        if "\\sigma" in formula: variables["sigmoid"] = "\\sigma(x)"
    elif label == "statistics":
        variables["data_point"] = "x_i"
        if "\\mu" in formula: variables["mean"] = "\\mu"
        if "\\nu" in formula: variables["mean_y"] = "\\nu"
        if "n" in formula: variables["sample_size"] = "n"
    elif label == "geometry":
        variables["set"] = "S"
        variables["element"] = "x"
        variables["universe"] = "\\Omega"
    else:
        if "x" in formula: variables["variable"] = "x"
        if re.search(r'\ba\b', formula): variables["parameter"] = "a"
        if re.search(r'\bn\b', formula): variables["order"] = "n"
    return variables if variables else {"variable": "x"}


def get_constraints(formula, label):
    """Tạo constraints thực sự liên quan đến công thức."""
    constraints = []
    if label == "integral":
        if "\\ln" in formula or "\\log" in formula or "ln" in formula:
            constraints.append("x > 0 (để logarit xác định)")
        if "\\frac{1}{" in formula:
            constraints.append("Mẫu số \\neq 0 (tránh chia cho 0)")
        if "\\sqrt" in formula:
            constraints.append("Biểu thức dưới dấu căn \\geq 0")
        if re.search(r'\ba\b', formula) or "ax" in formula:
            constraints.append("a \\neq 0")
        if "n\\ne -1" in formula or "n \\ne -1" in formula:
            constraints.append("n \\neq -1 \\text{ (trường hợp đặc biệt cho } \\int x^{-1}dx = \\ln|x|)")
        if "n\\ne 0" in formula:
            constraints.append("n \\neq 0")
        if not constraints:
            constraints.append("Tích phân hội tụ trên miền xác định tương ứng")
    elif label == "trigonometry":
        if "\\tan" in formula:
            constraints.append("\\theta \\neq \\frac{\\pi}{2} + k\\pi,\\; k \\in \\mathbb{Z}")
        if "\\cot" in formula:
            constraints.append("\\theta \\neq k\\pi,\\; k \\in \\mathbb{Z}")
        if "\\sec" in formula:
            constraints.append("\\cos\\theta \\neq 0")
        if "\\csc" in formula:
            constraints.append("\\sin\\theta \\neq 0")
        if not constraints:
            constraints.append("\\theta \\in \\mathbb{R}")
    elif label == "root":
        if "arccos" in formula or "arcsin" in formula:
            constraints.append("-1 \\leq x \\leq 1")
            constraints.append("\\sqrt{1-x^2} \\neq 0 \\Rightarrow |x| \\neq 1")
        elif "arcsec" in formula or "arccsc" in formula:
            constraints.append("|x| > 1 \\text{ (miền xác định của arcsec/arccsc)}")
            constraints.append("\\sqrt{x^2 - 1} \\neq 0 \\Rightarrow |x| \\neq 1")
        else:
            constraints.append("x \\in \\mathbb{R}")
    elif label == "linear_algebra":
        constraints.append("Ma trận A và vector x phải có chiều tương thích")
        constraints.append("A \\in \\mathbb{R}^{m \\times n},\\; x \\in \\mathbb{R}^n")
    elif label == "optimization":
        constraints.append("Hàm phải khả vi tại điểm đang xét")
        if "\\lambda" in formula:
            constraints.append("\\lambda \\geq 0 \\text{ (hệ số regularization không âm)}")
        if "\\sigma" in formula or "sigmoid" in formula:
            constraints.append("0 < \\sigma(x) < 1")
    elif label == "statistics":
        constraints.append("n > 0 (số mẫu phải dương)")
    elif label == "geometry":
        constraints.append("S, T \\subseteq \\Omega \\text{ (đều là tập con của không gian mẫu)}")
    else:
        constraints.append("Các biến phải thuộc miền xác định của công thức")
    return constraints


def get_negative_examples(formula, label):
    """Tạo negative examples cụ thể theo loại công thức."""
    negatives = []
    if label == "integral":
        if "e^{ax}" in formula:
            negatives.append("\\int e^{ax} dx = e^{ax} \\text{ (sai: quên hệ số 1/a)}")
            negatives.append("\\int e^{ax} dx = x e^{ax} \\text{ (sai: đây là kết quả dạng khác)}")
        elif "\\sin ax" in formula or "\\sin x" in formula:
            negatives.append("\\int \\sin ax \\, dx = \\cos ax \\text{ (sai dấu và thiếu hệ số)}")
        elif "\\cos ax" in formula or "\\cos x" in formula:
            negatives.append("\\int \\cos ax \\, dx = -\\sin ax \\text{ (sai dấu)}")
        elif "\\frac{1}{x}" in formula:
            negatives.append("\\int \\frac{1}{x} dx = \\frac{x^0}{0} \\text{ (sai: áp dụng sai quy tắc lũy thừa khi n=-1)}")
        elif "x^n" in formula:
            negatives.append("\\int x^n dx = x^n \\text{ (sai: quên chia cho n+1)}")
            negatives.append("\\int x^n dx = \\frac{x^{n+1}}{n} \\text{ (sai: mẫu số phải là n+1)}")
        else:
            negatives.append("Quên thêm hằng số C cho tích phân bất định")
            negatives.append("Nhầm hệ số hoặc dấu trong kết quả cuối")
    elif label == "trigonometry":
        negatives.append("\\sin^2\\theta + \\cos^2\\theta = 0 \\text{ (sai: bằng 1 không phải 0)}")
        negatives.append("\\sin(\\alpha + \\beta) = \\sin\\alpha \\cdot \\sin\\beta \\text{ (sai: không có cộng góc đơn giản)}")
    elif label == "root":
        negatives.append("\\frac{d}{dx}\\arcsin x = \\frac{1}{\\sqrt{1+x^2}} \\text{ (sai dấu trong căn)}")
        negatives.append("\\frac{d}{dx}\\arccos x = \\frac{1}{\\sqrt{1-x^2}} \\text{ (sai: thiếu dấu trừ)}")
    elif label == "linear_algebra":
        negatives.append("\\nabla(x^T A x) = Ax \\text{ (sai: thiếu hạng tử A^T x khi A không đối xứng)}")
        negatives.append("AB = BA \\text{ (sai nói chung: nhân ma trận không giao hoán)}")
    elif label == "optimization":
        negatives.append("\\nabla f = 0 \\text{ luôn là cực tiểu} \\text{ (sai: có thể là cực đại hoặc điểm yên ngựa)}")
    elif label == "statistics":
        negatives.append("\\text{Var}(X) = E[X] \\text{ (sai: phương sai \\neq kỳ vọng nói chung)}")
    elif label == "geometry":
        negatives.append("S \\cap T = S \\cup T \\text{ (sai: giao và hợp là hai phép toán khác nhau)}")
        negatives.append("x \\in S^c \\Leftrightarrow x \\in S \\text{ (sai: bù là phần ngoài S)}")
    else:
        negatives.append("Áp dụng sai thứ tự các phép toán hoặc nhầm công thức tương tự")
    return negatives


# ===========================================================================
# ENTRY CONVERSION
# ===========================================================================

def is_old_format(entry):
    keys = set(entry.keys())
    has_old = "formula" in keys and "label" in keys
    has_new = "id" in keys and "instruction" in keys
    return has_old and not has_new


def convert_entry(entry, index):
    formula = entry.get("formula", "")
    label = entry.get("label", "algebra")
    description = entry.get("description", "")
    latex = entry.get("latex", formula)

    if not formula or len(formula.strip()) < 3:
        return None

    formula_type = get_formula_type(label)
    difficulty = get_difficulty(formula, label)
    tags = extract_tags(formula, label)
    entry_id = make_id(formula, label, index, description)
    instruction = get_instruction(formula, label, description)
    instruction_variants = get_instruction_variants(instruction, label)
    steps = get_steps(formula, label)
    reasoning = get_reasoning(formula, label, instruction)
    variables = get_variables(formula, label)
    constraints = get_constraints(formula, label)
    negative_examples = get_negative_examples(formula, label)

    # Chuẩn hoá output bằng SymPy
    output_normalized = sympy_normalize_latex(latex)

    return {
        "id": entry_id,
        "instruction": instruction,
        "instruction_variants": instruction_variants,
        "input": latex,
        "steps": steps,
        "reasoning": reasoning,
        "output": latex,
        "output_normalized": output_normalized,
        "variables": variables,
        "constraints": constraints,
        "negative_examples": negative_examples,
        "type": formula_type,
        "difficulty": difficulty,
        "tags": tags
    }


def main():
    # Use backup as input so we rebuild from raw state
    backup_path = Path("datasheet_backup.json")
    output_path = Path("datasheet.json")

    src = backup_path if backup_path.exists() else Path("datasheet.json")
    print(f"Đọc từ: {src}")
    with open(src, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Tổng số entry gốc: {len(data)}")

    converted = 0
    kept = 0
    old_index = 0
    new_data = []

    for entry in data:
        if is_old_format(entry):
            old_index += 1
            new_entry = convert_entry(entry, old_index)
            if new_entry:
                new_data.append(new_entry)
                converted += 1
        else:
            new_data.append(entry)
            kept += 1

    # Dedup IDs: nếu trùng thì thêm _2, _3, ...
    seen_ids = {}
    for entry in new_data:
        raw_id = entry.get("id", "")
        if not raw_id:
            continue
        if raw_id not in seen_ids:
            seen_ids[raw_id] = 1
        else:
            seen_ids[raw_id] += 1
            entry["id"] = f"{raw_id}_{seen_ids[raw_id]}"

    dup_count = sum(1 for v in seen_ids.values() if v > 1)
    print(f"\nKết quả:")
    print(f"  Chuyển đổi: {converted}")
    print(f"  Giữ nguyên: {kept}")
    print(f"  Tổng mới:   {len(new_data)}")
    print(f"  ID trùng đã xử lý: {dup_count} nhóm")

    print(f"\nGhi vào {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print("Hoàn thành!")


if __name__ == "__main__":
    main()
