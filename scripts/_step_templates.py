"""Template steps theo từng chủ đề toán học.

Mỗi template là một function nhận (instruction, output, topic) và trả về list of steps.
Template có chèn output vào step cuối để người đọc thấy kết quả cụ thể.
"""
import re
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def _clean_output_latex(out):
    """Trích xuất phần LaTeX chính từ output (bỏ \\text{...})."""
    out = out.strip()
    # Nếu output là "\text{...}" đơn thuần
    m = re.match(r"^\\text\{(.+)\}$", out)
    if m:
        return m.group(1)
    # Nếu output chứa ký hiệu nối bằng \text
    return out


def _extract_keywords(output):
    """Trích xuất các ký hiệu LaTeX chính trong output."""
    keywords = []
    if "\\frac" in output:
        keywords.append("phân số")
    if "\\int" in output:
        keywords.append("tích phân")
    if "\\sum" in output:
        keywords.append("tổng")
    if "\\sqrt" in output:
        keywords.append("căn bậc hai")
    if "\\sin" in output or "\\cos" in output or "\\tan" in output or "\\cot" in output:
        keywords.append("hàm lượng giác")
    if "\\lim" in output:
        keywords.append("giới hạn")
    if "\\log" in output or "\\ln" in output:
        keywords.append("logarit")
    if "^{" in output:
        keywords.append("lũy thừa")
    if "_" in output:
        keywords.append("chỉ số dưới")
    if "\\nabla" in output or "\\partial" in output:
        keywords.append("đạo hàm riêng")
    if "\\begin{matrix}" in output or "\\begin{pmatrix}" in output or "\\begin{bmatrix}" in output:
        keywords.append("ma trận")
    if "\\vec" in output or "\\overrightarrow" in output:
        keywords.append("vectơ")
    return keywords


# ============ TEMPLATE THEO TOPIC ============

def template_fraction(instruction, output):
    """Phân số: cộng/trừ/nhân/chia, cùng mẫu/khác mẫu."""
    out_clean = _clean_output_latex(output)
    if "cùng mẫu" in instruction.lower():
        if "trừ" in instruction.lower():
            return [
                "Bước 1: Kiểm tra hai phân số có cùng mẫu số.",
                "Bước 2: Vì cùng mẫu, giữ nguyên mẫu số và thực hiện phép trừ trên tử số.",
                "Bước 3: Trình bày kết quả dưới dạng phân số với tử số mới và mẫu số chung.",
                f"Bước 4: Rút gọn nếu có thể và viết đáp án: $${out_clean}$$",
            ]
        elif "cộng" in instruction.lower():
            return [
                "Bước 1: Kiểm tra hai phân số có cùng mẫu số.",
                "Bước 2: Vì cùng mẫu, giữ nguyên mẫu số và thực hiện phép cộng trên tử số.",
                "Bước 3: Trình bày kết quả dưới dạng phân số với tử số mới và mẫu số chung.",
                f"Bước 4: Rút gọn nếu có thể và viết đáp án: $${out_clean}$$",
            ]
        elif "nhân" in instruction.lower():
            return [
                "Bước 1: Để nhân hai phân số, ta nhân tử với tử và mẫu với mẫu.",
                "Bước 2: Tính tích tử số và tích mẫu số.",
                "Bước 3: Trình bày kết quả dưới dạng phân số mới.",
                f"Bước 4: Rút gọn nếu có thể và viết đáp án: $${out_clean}$$",
            ]
    elif "khác mẫu" in instruction.lower():
        return [
            "Bước 1: Xác định hai phân số có mẫu số khác nhau.",
            "Bước 2: Quy đồng mẫu số bằng cách tìm bội chung nhỏ nhất (BCNN) của hai mẫu.",
            "Bước 3: Đưa hai phân số về cùng mẫu rồi thực hiện phép tính trên tử số.",
            f"Bước 4: Rút gọn và viết đáp án: $${out_clean}$$",
        ]
    # Default
    return [
        "Bước 1: Xác định tử số và mẫu số của từng phân số.",
        "Bước 2: Kiểm tra điều kiện mẫu số khác 0 và quy đồng nếu cần.",
        "Bước 3: Thực hiện phép tính (cộng/trừ/nhân/chia) theo quy tắc phân số.",
        f"Bước 4: Rút gọn kết quả và viết đáp án: $${out_clean}$$",
    ]


def template_equation(instruction, output):
    """Phương trình - các dạng cơ bản."""
    out_clean = _clean_output_latex(output)
    if "bậc nhất" in instruction.lower() or "bậc 1" in instruction.lower():
        return [
            "Bước 1: Đưa phương trình về dạng tổng quát ax + b = 0 (a ≠ 0).",
            "Bước 2: Chuyển vế hằng số b sang vế phải: ax = -b.",
            "Bước 3: Chia cả hai vế cho hệ số a để tìm nghiệm x.",
            f"Bước 4: Kết luận nghiệm và viết đáp án: $${out_clean}$$",
        ]
    if "bậc hai" in instruction.lower() or "bậc 2" in instruction.lower():
        return [
            "Bước 1: Đưa phương trình về dạng ax² + bx + c = 0 (a ≠ 0).",
            "Bước 2: Tính biệt thức Δ = b² - 4ac.",
            "Bước 3: Tùy Δ: nếu Δ < 0 vô nghiệm, Δ = 0 nghiệm kép, Δ > 0 hai nghiệm.",
            "Bước 4: Áp dụng công thức nghiệm và kết luận.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "mũ" in instruction.lower():
        return [
            "Bước 1: Đặt phương trình mũ ở dạng a^f(x) = b^g(x) hoặc a^f(x) = c.",
            "Bước 2: Đồng nhất cơ số hoặc đưa về cùng cơ số.",
            "Bước 3: Khi đã cùng cơ số, cho số mũ bằng nhau: f(x) = g(x).",
            "Bước 4: Giải phương trình f(x) = g(x) và kiểm tra điều kiện xác định.",
            f"Bước 5: Kết luận nghiệm: $${out_clean}$$",
        ]
    # Default phương trình tổng quát
    return [
        "Bước 1: Đọc kỹ phương trình và xác định dạng (tuyến tính, bậc hai, mũ, logarit...).",
        "Bước 2: Biến đổi phương trình về dạng chuẩn bằng các phép toán tương đương.",
        "Bước 3: Áp dụng công thức nghiệm phù hợp với dạng phương trình.",
        "Bước 4: Kiểm tra nghiệm có thỏa điều kiện xác định không.",
        f"Bước 5: Kết luận nghiệm: $${out_clean}$$",
    ]


def template_derivative(instruction, output):
    """Đạo hàm - các dạng hàm."""
    out_clean = _clean_output_latex(output)
    if "hàm hợp" in instruction.lower() or "chain rule" in instruction.lower():
        return [
            "Bước 1: Nhận diện hàm hợp f(g(x)) với hàm ngoài f và hàm trong g.",
            "Bước 2: Tính đạo hàm hàm ngoài f'(u) với u = g(x), giữ x như hằng.",
            "Bước 3: Tính đạo hàm hàm trong g'(x).",
            "Bước 4: Nhân hai đạo hàm theo công thức chain rule.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "tích" in instruction.lower() and "thương" in instruction.lower():
        return [
            "Bước 1: Nhận diện hàm dạng u(x)·v(x)/w(x) hoặc u(x)/v(x).",
            "Bước 2: Áp dụng quy tắc đạo hàm thương (u/v)' = (u'v - uv')/v².",
            "Bước 3: Tính đạo hàm từng phần tử.",
            "Bước 4: Kết hợp kết quả theo quy tắc tích-thương.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "lượng giác" in instruction.lower():
        return [
            "Bước 1: Nhận diện hàm lượng giác (sin, cos, tan, cot) và hàm ngược.",
            "Bước 2: Áp dụng công thức đạo hàm chuẩn cho hàm lượng giác.",
            "Bước 3: Nếu là hàm hợp, áp dụng chain rule.",
            "Bước 4: Rút gọn biểu thức cuối.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    # Default
    return [
        "Bước 1: Xác định dạng hàm số cần tính đạo hàm.",
        "Bước 2: Áp dụng quy tắc đạo hàm phù hợp (tổng, tích, thương, hàm hợp).",
        "Bước 3: Tính đạo hàm từng thành phần.",
        "Bước 4: Kết hợp và rút gọn kết quả.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_integral(instruction, output):
    """Tích phân - các dạng cơ bản."""
    out_clean = _clean_output_latex(output)
    if "xác định" in instruction.lower() or "cận" in instruction.lower():
        return [
            "Bước 1: Xác định hàm dưới dấu tích phân và cận tích phân (a, b).",
            "Bước 2: Tìm một nguyên hàm F(x) của hàm dưới dấu tích phân.",
            "Bước 3: Tính giá trị F(b) - F(a) theo công thức Newton-Leibniz.",
            "Bước 4: Kết luận giá trị tích phân xác định.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "bộ phận" in instruction.lower() or "từng phần" in instruction.lower():
        return [
            "Bước 1: Chọn u và dv trong tích phân ∫u·dv, ưu tiên u là hàm dễ đạo hàm.",
            "Bước 2: Tính du = u'dx và v = ∫dv.",
            "Bước 3: Áp dụng công thức ∫u·dv = uv - ∫v·du.",
            "Bước 4: Tính tích phân mới ∫v·du và rút gọn.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "đổi biến" in instruction.lower():
        return [
            "Bước 1: Chọn biến mới t = g(x) sao cho biểu thức dưới dấu tích phân đơn giản hơn.",
            "Bước 2: Tính dt = g'(x)dx và biểu diễn dx theo dt.",
            "Bước 3: Thay thế và đổi cận tích phân (nếu có).",
            "Bước 4: Tính tích phân theo biến mới.",
            "Bước 5: Thay ngược biến và kết luận.",
            f"Bước 6: Trình bày đáp án: $${out_clean}$$",
        ]
    # Default
    return [
        "Bước 1: Xác định dạng tích phân và hàm dưới dấu tích phân.",
        "Bước 2: Chọn phương pháp: đổi biến, từng phần, hay dùng nguyên hàm cơ bản.",
        "Bước 3: Thực hiện các phép biến đổi cần thiết.",
        "Bước 4: Tính tích phân và rút gọn kết quả.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_trigonometric(instruction, output):
    """Lượng giác - đẳng thức, hệ thức."""
    out_clean = _clean_output_latex(output)
    if "định lý" in instruction.lower() or "hệ thức" in instruction.lower() or "đẳng thức" in instruction.lower():
        return [
            "Bước 1: Nhận diện đẳng thức hoặc hệ thức lượng giác cần chứng minh/sử dụng.",
            "Bước 2: Xác định các thành phần: sin, cos, tan, cot của các góc liên quan.",
            "Bước 3: Áp dụng các công thức lượng giác cơ bản (Pythagoras, công thức cộng, góc đôi).",
            "Bước 4: Biến đổi vế này về vế kia hoặc rút gọn về dạng chuẩn.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "phương trình" in instruction.lower():
        return [
            "Bước 1: Đưa phương trình lượng giác về dạng cơ bản (đồng nhất cơ số).",
            "Bước 2: Áp dụng công thức lượng giác để rút gọn.",
            "Bước 3: Giải phương trình lượng giác cơ bản (sin/cos/tan = a).",
            "Bước 4: Tổng quát nghiệm và kiểm tra trong khoảng nếu cần.",
            f"Bước 5: Kết luận nghiệm: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định yếu tố lượng giác sin, cos, tan, cot.",
        "Bước 2: Áp dụng công thức phù hợp với dạng bài.",
        "Bước 3: Biến đổi biểu thức theo quy tắc lượng giác.",
        "Bước 4: Rút gọn kết quả.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_exponential(instruction, output):
    """Hàm mũ và lũy thừa."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()
    if "logarit" in instruction.lower() or "log" in instruction.lower():
        return [
            "Bước 1: Nhận diện dạng lũy thừa có liên quan đến logarit.",
            "Bước 2: Áp dụng định nghĩa logarit: log_a(b) = c ⇔ a^c = b.",
            "Bước 3: Biến đổi biểu thức theo tính chất lũy thừa-logarit.",
            "Bước 4: Rút gọn kết quả.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "tích" in instr_lower and "cơ số" in instr_lower:
        return [
            "Bước 1: Nhận diện hai lũy thừa có cùng cơ số: a^m · a^n.",
            "Bước 2: Áp dụng quy tắc: a^m · a^n = a^(m+n).",
            "Bước 3: Cộng các số mũ và giữ nguyên cơ số.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "thương" in instr_lower and "cơ số" in instr_lower:
        return [
            "Bước 1: Nhận diện hai lũy thừa có cùng cơ số ở dạng thương: a^m / a^n.",
            "Bước 2: Áp dụng quy tắc: a^m / a^n = a^(m-n).",
            "Bước 3: Trừ các số mũ và giữ nguyên cơ số.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "lũy thừa của lũy thừa" in instr_lower or "lũy thừa" in instr_lower and "của một lũy thừa" in instr_lower:
        return [
            "Bước 1: Nhận diện lũy thừa có dạng (a^m)^n.",
            "Bước 2: Áp dụng quy tắc: (a^m)^n = a^(m·n).",
            "Bước 3: Nhân các số mũ.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định dạng lũy thừa a^x hoặc a^(f(x)).",
        "Bước 2: Áp dụng tính chất lũy thừa: a^m · a^n = a^(m+n), (a^m)^n = a^(m·n).",
        "Bước 3: Biến đổi biểu thức theo quy tắc lũy thừa.",
        "Bước 4: Rút gọn kết quả.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_logarithm(instruction, output):
    """Logarit."""
    out_clean = _clean_output_latex(output)
    if "định nghĩa" in instruction.lower():
        return [
            "Bước 1: Nhắc lại định nghĩa logarit: log_a(b) = c khi và chỉ khi a^c = b.",
            "Bước 2: Xác định cơ số a > 0, a ≠ 1 và đối số b > 0.",
            "Bước 3: Trình bày định nghĩa dưới dạng công thức.",
            f"Bước 4: Kết luận: $${out_clean}$$",
        ]
    if "phương trình" in instruction.lower():
        return [
            "Bước 1: Đặt điều kiện xác định: cơ số > 0 và ≠ 1, đối số > 0.",
            "Bước 2: Biến đổi phương trình về dạng log_a(f(x)) = b.",
            "Bước 3: Chuyển về phương trình mũ: f(x) = a^b.",
            "Bước 4: Giải và kiểm tra điều kiện.",
            f"Bước 5: Kết luận nghiệm: $${out_clean}$$",
        ]
    return [
        "Bước 1: Nhận diện biểu thức chứa logarit.",
        "Bước 2: Xác định cơ số và đối số, kiểm tra điều kiện xác định.",
        "Bước 3: Áp dụng tính chất logarit: log(a·b) = log(a) + log(b), log(a/b) = log(a) - log(b), log(a^n) = n·log(a).",
        "Bước 4: Biến đổi và rút gọn.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_matrix(instruction, output):
    """Ma trận."""
    out_clean = _clean_output_latex(output)
    if "định thức" in instruction.lower() or "det" in instruction.lower():
        return [
            "Bước 1: Xác định ma trận vuông cấp n cần tính định thức.",
            "Bước 2: Áp dụng công thức định thức (cấp 2: ad - bc, cấp 3: Sarrus, cấp n: khai triển Laplace).",
            "Bước 3: Tính toán từng phần tử theo công thức.",
            "Bước 4: Kết luận giá trị định thức.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "nghịch đảo" in instruction.lower() or "^-1" in output:
        return [
            "Bước 1: Tính định thức của ma trận, kiểm tra định thức khác 0.",
            "Bước 2: Tìm ma trận phụ hợp (adjugate matrix).",
            "Bước 3: Áp dụng công thức A^(-1) = adj(A) / det(A).",
            "Bước 4: Rút gọn các phần tử của ma trận nghịch đảo.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "nhân" in instruction.lower():
        return [
            "Bước 1: Xác định kích thước hai ma trận A (m×n) và B (n×p).",
            "Bước 2: Tính từng phần tử (AB)_ij = Σ_k A_ik · B_kj.",
            "Bước 3: Trình bày kết quả dưới dạng ma trận C có kích thước m×p.",
            f"Bước 4: Kết luận: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định kích thước và các phần tử của ma trận.",
        "Bước 2: Áp dụng phép toán ma trận phù hợp (cộng, nhân, nghịch đảo, chuyển vị).",
        "Bước 3: Tính toán từng phần tử.",
        "Bước 4: Trình bày kết quả dưới dạng ma trận.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_vector(instruction, output):
    """Vectơ."""
    out_clean = _clean_output_latex(output)
    if "gradient" in instruction.lower():
        return [
            "Bước 1: Xác định hàm nhiều biến f(x₁, x₂, ..., x_n).",
            "Bước 2: Tính đạo hàm riêng ∂f/∂x_i với từng biến x_i.",
            "Bước 3: Ghép các đạo hàm riêng thành vectơ gradient ∇f.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "tích vô hướng" in instruction.lower() or "dot" in instruction.lower():
        return [
            "Bước 1: Xác định hai vectơ u = (u₁, u₂, ...) và v = (v₁, v₂, ...).",
            "Bước 2: Áp dụng công thức u·v = u₁v₁ + u₂v₂ + ...",
            "Bước 3: Tính tổng các tích từng cặp thành phần.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "tích có hướng" in instruction.lower() or "cross" in instruction.lower():
        return [
            "Bước 1: Xác định hai vectơ u và v trong không gian 3D.",
            "Bước 2: Lập định thức với i, j, k là đơn vị vectơ.",
            "Bước 3: Tính các thành phần (u₂v₃-u₃v₂, u₃v₁-u₁v₃, u₁v₂-u₂v₁).",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định các vectơ và phép toán cần thực hiện.",
        "Bước 2: Áp dụng công thức tương ứng (cộng, trừ, tích vô hướng, tích có hướng).",
        "Bước 3: Tính toán từng thành phần.",
        f"Bước 4: Trình bày đáp án: $${out_clean}$$",
    ]


def template_polynomial(instruction, output):
    """Đa thức."""
    out_clean = _clean_output_latex(output)
    if "định nghĩa" in instruction.lower() or "tổng quát" in instruction.lower():
        return [
            "Bước 1: Nhắc lại định nghĩa đa thức bậc n: P(x) = a_n x^n + ... + a_1 x + a_0.",
            "Bước 2: Liệt kê các hệ số a_n, a_{n-1}, ..., a_0 và bậc n.",
            "Bước 3: Trình bày dạng tổng quát của đa thức.",
            f"Bước 4: Kết luận: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định bậc và hệ số của đa thức.",
        "Bước 2: Áp dụng phép toán đa thức phù hợp (cộng, trừ, nhân, chia, phân tích).",
        "Bước 3: Thực hiện biến đổi từng bước.",
        "Bước 4: Rút gọn về dạng chuẩn.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_limit(instruction, output):
    """Giới hạn."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()
    if "tồn tại" in instr_lower:
        return [
            "Bước 1: Tính giới hạn trái lim_{x→y⁻} f(x).",
            "Bước 2: Tính giới hạn phải lim_{x→y⁺} f(x).",
            "Bước 3: So sánh hai giới hạn, nếu bằng nhau thì giới hạn tồn tại.",
            f"Bước 4: Kết luận: $${out_clean}$$",
        ]
    if "\\infty" in output or "vô cùng" in instr_lower:
        return [
            "Bước 1: Xác định dạng giới hạn khi x → ∞ (hoặc -∞).",
            "Bước 2: Chia cả tử và mẫu cho lũy thừa bậc cao nhất của x.",
            "Bước 3: Tính giới hạn từng phần khi x → ∞.",
            "Bước 4: Kết luận giá trị giới hạn.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "vô định" in instr_lower or "0/0" in output or "\\frac{0}{0}" in output:
        return [
            "Bước 1: Xác định giới hạn và kiểm tra dạng vô định (0/0, ∞/∞).",
            "Bước 2: Áp dụng kỹ thuật phù hợp: nhân liên hợp, rút gọn, L'Hôpital, khai triển Taylor.",
            "Bước 3: Thực hiện biến đổi để loại bỏ dạng vô định.",
            "Bước 4: Tính giới hạn sau khi đã xử lý dạng vô định.",
            f"Bước 5: Kết luận: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định dạng giới hạn (khi x→0, x→∞, hay x→a cụ thể).",
        "Bước 2: Kiểm tra dạng vô định (0/0, ∞/∞, 0·∞, ...) nếu có.",
        "Bước 3: Áp dụng kỹ thuật phù hợp: rút gọn, nhân liên hợp, L'Hôpital, khai triển Taylor.",
        "Bước 4: Tính giá trị giới hạn.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_complex(instruction, output):
    """Số phức."""
    out_clean = _clean_output_latex(output)
    return [
        "Bước 1: Nhắc lại định nghĩa số phức z = a + bi với i = √(-1).",
        "Bước 2: Xác định phần thực a và phần ảo b.",
        "Bước 3: Áp dụng phép toán số phức (cộng, trừ, nhân, chia, lũy thừa).",
        "Bước 4: Trình bày kết quả dưới dạng a + bi.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_function(instruction, output):
    """Hàm số."""
    out_clean = _clean_output_latex(output)
    if "tuyến tính" in instruction.lower() or "bậc nhất" in instruction.lower():
        return [
            "Bước 1: Nhận diện hàm bậc nhất f(x) = ax + b (a ≠ 0).",
            "Bước 2: Xác định hệ số góc a và tung độ gốc b.",
            "Bước 3: Trình bày dạng tổng quát của hàm tuyến tính.",
            f"Bước 4: Kết luận: $${out_clean}$$",
        ]
    if "bậc hai" in instruction.lower():
        return [
            "Bước 1: Nhận diện hàm bậc hai f(x) = ax² + bx + c (a ≠ 0).",
            "Bước 2: Xác định các hệ số a, b, c.",
            "Bước 3: Tính đỉnh parabol, trục đối xứng nếu cần.",
            "Bước 4: Trình bày dạng tổng quát.",
            f"Bước 5: Kết luận: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định dạng hàm số và tập xác định.",
        "Bước 2: Phân tích các đặc điểm (điểm cực trị, điểm uốn, tiệm cận) nếu cần.",
        "Bước 3: Trình bày dạng tổng quát của hàm.",
        f"Bước 4: Kết luận: $${out_clean}$$",
    ]


def template_geometry_plane(instruction, output):
    """Hình học phẳng."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()

    if "tổng ba góc" in instr_lower or "tổng 3 góc" in instr_lower:
        return [
            "Bước 1: Nhắc lại định lý: tổng ba góc trong một tam giác bằng 180°.",
            "Bước 2: Xác định ba góc của tam giác đang xét.",
            "Bước 3: Áp dụng định lý để thiết lập phương trình tổng ba góc.",
            "Bước 4: Rút ra kết luận về tổng ba góc.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "đường trung trực" in instr_lower or "cách đều" in instr_lower:
        return [
            "Bước 1: Nhắc lại định nghĩa: đường trung trực của đoạn thẳng AB là tập hợp các điểm cách đều A và B.",
            "Bước 2: Đặt Z là điểm bất kỳ trên đường trung trực.",
            "Bước 3: Theo định nghĩa: ZX = ZY.",
            "Bước 4: Kết luận quỹ tích các điểm Z cách đều X và Y.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "tam giác" in instr_lower:
        return [
            "Bước 1: Xác định loại tam giác (vuông, cân, đều, thường).",
            "Bước 2: Xác định các yếu tố: cạnh, góc, đường cao, trung tuyến, phân giác.",
            "Bước 3: Áp dụng định lý hoặc công thức phù hợp.",
            "Bước 4: Tính toán giá trị yêu cầu.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "đường tròn" in instr_lower:
        return [
            "Bước 1: Xác định tâm và bán kính đường tròn.",
            "Bước 2: Áp dụng công thức phù hợp (chu vi, diện tích, phương trình đường tròn).",
            "Bước 3: Tính toán giá trị yêu cầu.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "diện tích" in instr_lower or "chu vi" in instr_lower:
        return [
            "Bước 1: Xác định hình phẳng cần tính (vuông, chữ nhật, tam giác, tròn, ...).",
            "Bước 2: Liệt kê các đại lượng cần thiết (cạnh, bán kính, đường kính).",
            "Bước 3: Áp dụng công thức diện tích hoặc chu vi tương ứng.",
            "Bước 4: Tính toán giá trị.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "định lý" in instr_lower or "tính chất" in instr_lower:
        return [
            "Bước 1: Nhắc lại định lý/tính chất hình học liên quan.",
            "Bước 2: Xác định các yếu tố đã cho và cần tìm.",
            "Bước 3: Áp dụng định lý vào bài toán cụ thể.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Phân tích hình học và xác định các yếu tố đã cho.",
        "Bước 2: Vẽ hình minh họa nếu cần.",
        "Bước 3: Áp dụng công thức hoặc định lý hình học phù hợp.",
        "Bước 4: Tính toán và rút gọn kết quả.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_geometry_solid(instruction, output):
    """Hình học không gian."""
    out_clean = _clean_output_latex(output)
    if "thể tích" in instruction.lower():
        shape = ""
        if "cầu" in instruction.lower():
            shape = "hình cầu"
        elif "nón" in instruction.lower():
            shape = "hình nón"
        elif "trụ" in instruction.lower():
            shape = "hình trụ"
        elif "chóp" in instruction.lower():
            shape = "hình chóp"
        elif "lăng trụ" in instruction.lower():
            shape = "hình lăng trụ"
        elif "hộp" in instruction.lower() or "chữ nhật" in instruction.lower():
            shape = "hình hộp chữ nhật"
        elif "lập phương" in instruction.lower():
            shape = "hình lập phương"
        return [
            f"Bước 1: Xác định {shape} và các đại lượng đã cho (bán kính, chiều cao, cạnh đáy).",
            "Bước 2: Áp dụng công thức tính thể tích phù hợp với từng hình.",
            "Bước 3: Tính diện tích đáy (nếu cần).",
            "Bước 4: Tính thể tích bằng công thức V = (1/3)·S_đáy·h hoặc công thức đặc thù.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định hình không gian và các yếu tố đã cho.",
        "Bước 2: Áp dụng công thức thể tích hoặc diện tích xung quanh phù hợp.",
        "Bước 3: Tính toán từng phần.",
        f"Bước 4: Trình bày đáp án: $${out_clean}$$",
    ]


def template_algebra_basic(instruction, output):
    """Đại số cơ bản - tổng quát."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()

    if "phân phối" in instr_lower or "nhân tử chung" in instr_lower:
        return [
            "Bước 1: Nhận diện biểu thức có dạng a·b + a·c (tích chung của một nhân tử).",
            "Bước 2: Xác định nhân tử chung xuất hiện ở tất cả các hạng tử.",
            "Bước 3: Đặt nhân tử chung ra ngoài dấu ngoặc, giữ lại phần còn lại trong ngoặc.",
            f"Bước 4: Kiểm tra bằng cách phân phối ngược: $${out_clean}$$",
        ]
    if "giao hoán" in instr_lower:
        return [
            "Bước 1: Nhắc lại tính chất giao hoán: a·b = b·a hoặc a+b = b+a.",
            "Bước 2: Xác định phép toán trong bài (cộng hay nhân).",
            "Bước 3: Áp dụng tính chất giao hoán để đổi chỗ các thừa số (hoặc số hạng).",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "kết hợp" in instr_lower:
        return [
            "Bước 1: Nhắc lại tính chất kết hợp: (a·b)·c = a·(b·c) hoặc (a+b)+c = a+(b+c).",
            "Bước 2: Xác định cách nhóm các thừa số (hoặc số hạng).",
            "Bước 3: Áp dụng tính chất kết hợp để tính toán theo thứ tự bất kỳ.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "đẳng thức" in instr_lower or "đồng nhất" in instr_lower:
        return [
            "Bước 1: Đọc kỹ đẳng thức cần chứng minh hoặc sử dụng.",
            "Bước 2: Xác định biến và hằng số trong đẳng thức.",
            "Bước 3: Áp dụng các tính chất và quy tắc đại số để biến đổi.",
            "Bước 4: Rút gọn và kiểm tra tính đúng đắn của đẳng thức.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "đơn giản hóa" in instr_lower or "rút gọn biểu thức" in instr_lower:
        return [
            "Bước 1: Xác định các phép toán trong biểu thức (cộng, trừ, nhân, chia, lũy thừa).",
            "Bước 2: Thực hiện phép tính trong ngoặc trước (theo thứ tự ưu tiên).",
            "Bước 3: Áp dụng tính chất giao hoán, kết hợp, phân phối để nhóm hạng tử.",
            "Bước 4: Cộng/trừ các hạng tử đồng dạng.",
            f"Bước 5: Trình bày đáp án dạng rút gọn: $${out_clean}$$",
        ]
    if "tích" in instr_lower and "hai biểu thức" in instr_lower:
        return [
            "Bước 1: Xác định hai biểu thức dạng tích cần nhân với nhau.",
            "Bước 2: Áp dụng tính chất giao hoán và kết hợp để nhóm các thừa số.",
            "Bước 3: Nhân từng thừa số trong biểu thức thứ nhất với từng thừa số trong biểu thức thứ hai.",
            "Bước 4: Cộng các tích thu được.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "sigma" in instr_lower or "\\sum" in output or "tổng" in instr_lower:
        return [
            "Bước 1: Xác định biểu thức dưới dấu tổng và cận tổng (i từ a đến b).",
            "Bước 2: Kiểm tra xem biểu thức có phụ thuộc vào chỉ số tổng hay không.",
            "Bước 3: Nếu không phụ thuộc, đưa ra ngoài dấu tổng và nhân với số lượng hạng tử (b - a + 1).",
            "Bước 4: Nếu phụ thuộc, áp dụng công thức tổng tương ứng (tổng i, tổng i², ...).",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "biểu thức đại số" in instr_lower or "khái niệm" in instr_lower or "định nghĩa" in instr_lower:
        return [
            "Bước 1: Nhắc lại khái niệm: biểu thức đại số gồm số, biến, phép toán (+, -, ×, ÷, lũy thừa).",
            "Bước 2: Xác định dạng biểu thức (đơn thức, đa thức, phân thức, ...).",
            "Bước 3: Phân tích các thành phần của biểu thức.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "cộng" in instr_lower or "trừ" in instr_lower or "nhân" in instr_lower or "chia" in instr_lower:
        return [
            "Bước 1: Xác định hai biểu thức cần thực hiện phép tính.",
            "Bước 2: Kiểm tra các điều kiện (quy đồng mẫu nếu cần).",
            "Bước 3: Thực hiện phép tính theo quy tắc tương ứng.",
            f"Bước 4: Rút gọn kết quả: $${out_clean}$$",
        ]
    # Default cho algebra_basic
    return [
        "Bước 1: Đọc kỹ biểu thức và xác định các thành phần (biến, hằng số, phép toán).",
        "Bước 2: Kiểm tra điều kiện xác định (mẫu số khác 0, biểu thức trong căn không âm, ...).",
        "Bước 3: Áp dụng các quy tắc đại số: phân phối, kết hợp, giao hoán, tách hạng tử.",
        "Bước 4: Biến đổi biểu thức từng bước một cách có hệ thống.",
        "Bước 5: Rút gọn về dạng chuẩn cuối cùng.",
        f"Bước 6: Trình bày đáp án: $${out_clean}$$",
    ]


def template_default(instruction, output):
    """Template mặc định khi không phân loại được."""
    out_clean = _clean_output_latex(output)
    keywords = _extract_keywords(output)
    kw_str = ", ".join(keywords[:3]) if keywords else "các yếu tố toán học"
    return [
        "Bước 1: Đọc kỹ đề bài và xác định dạng toán.",
        f"Bước 2: Nhận diện các yếu tố chính: {kw_str}.",
        "Bước 3: Áp dụng công thức hoặc quy tắc toán học phù hợp.",
        "Bước 4: Thực hiện biến đổi từng bước.",
        "Bước 5: Rút gọn và kiểm tra kết quả.",
        f"Bước 6: Trình bày đáp án: $${out_clean}$$",
    ]


# ============ REASONING TEMPLATES ============

REASONING_BY_TOPIC = {
    "fraction": "Bài toán này thuộc dạng phân số. Khi giải, ta cần xác định rõ tử số, mẫu số và các điều kiện về mẫu số (khác 0). Cần nhớ quy tắc cộng/trừ phân số (cùng mẫu thì cộng/trừ tử, khác mẫu phải quy đồng) và quy tắc nhân/chia phân số (nhân tử với tử, mẫu với mẫu; chia là nhân với nghịch đảo). Kết quả cần được rút gọn về dạng tối giản.",
    "equation": "Bài toán này thuộc dạng phương trình. Đầu tiên cần xác định dạng phương trình (tuyến tính, bậc hai, mũ, logarit, ...). Sau đó đặt điều kiện xác định và biến đổi phương trình về dạng chuẩn bằng các phép toán tương đương. Áp dụng công thức nghiệm phù hợp và luôn kiểm tra nghiệm có thỏa điều kiện xác định không.",
    "derivative": "Bài toán này thuộc dạng đạo hàm. Để tính đạo hàm, ta cần xác định dạng hàm số (đơn giản, hợp, tích, thương, hàm ẩn) rồi áp dụng quy tắc đạo hàm tương ứng: (x^n)' = nx^(n-1), (uv)' = u'v + uv', (u/v)' = (u'v-uv')/v², (f∘g)' = f'(g)·g'. Kết quả thường được đơn giản hóa để có dạng dễ sử dụng.",
    "integral": "Bài toán này thuộc dạng tích phân. Có ba phương pháp chính: (1) Dùng công thức nguyên hàm cơ bản, (2) Đổi biến số - phù hợp khi hàm dưới dấu tích phân có dạng f(g(x))·g'(x), (3) Tích phân từng phần ∫u·dv = uv - ∫v·du - phù hợp với tích của hai hàm. Với tích phân xác định, áp dụng công thức Newton-Leibniz F(b) - F(a).",
    "trigonometric": "Bài toán này thuộc dạng lượng giác. Các công thức nền tảng cần nhớ: sin²x + cos²x = 1, các công thức cộng/góc đôi (sin(a±b), cos(a±b), tan(a±b)), công thức biến đổi tích thành tổng và ngược lại. Khi giải phương trình lượng giác, cần đưa về dạng cơ bản rồi tổng quát nghiệm.",
    "exponential": "Bài toán này thuộc dạng hàm mũ/lũy thừa. Tính chất quan trọng: a^m · a^n = a^(m+n), (a^m)^n = a^(m·n), a^(-n) = 1/a^n, a^(m/n) = ⁿ√(a^m). Hàm mũ có đạo hàm (a^x)' = a^x·ln(a) và tích phân ∫a^x dx = a^x/ln(a) + C.",
    "logarithm": "Bài toán này thuộc dạng logarit. Định nghĩa: log_a(b) = c ⇔ a^c = b. Các tính chất: log(a·b) = log(a) + log(b), log(a/b) = log(a) - log(b), log(a^n) = n·log(a), đổi cơ số log_a(b) = log_c(b)/log_c(a). Điều kiện xác định: cơ số > 0 và ≠ 1, đối số > 0.",
    "matrix": "Bài toán này thuộc dạng ma trận. Các phép toán cơ bản: cộng/trừ (cùng kích thước), nhân (số cột A = số hàng B), chuyển vị (A^T)_ij = A_ji. Với ma trận vuông: định thức det(A) (đặc biệt cho cấp 2, 3), ma trận nghịch đảo A^(-1) = adj(A)/det(A) khi det(A) ≠ 0.",
    "vector": "Bài toán này thuộc dạng vectơ. Hai phép toán chính: (1) Tích vô hướng u·v = |u||v|cos(θ) = u₁v₁ + u₂v₂ + u₃v₃ cho kết quả là số vô hướng, (2) Tích có hướng u×v cho vectơ vuông góc với cả u và v, có độ lớn |u||v|sin(θ). Gradient ∇f là vectơ các đạo hàm riêng, chỉ hướng tăng nhanh nhất của hàm.",
    "polynomial": "Bài toán này thuộc dạng đa thức. Đa thức bậc n có dạng P(x) = a_n x^n + ... + a_1 x + a_0. Các thao tác: cộng/trừ (cộng/trừ hệ số cùng bậc), nhân (nhân từng hạng tử), chia (dùng thuật toán chia đa thức, thu được thương và dư), phân tích nhân tử (tách thành tích các đa thức bậc thấp hơn).",
    "limit": "Bài toán này thuộc dạng giới hạn. Các dạng vô định cần xử lý: 0/0 (rút gọn, nhân liên hợp, L'Hôpital), ∞/∞ (chia cho bậc cao nhất), 0·∞ (đổi về dạng 0/0 hoặc ∞/∞). Khi tính giới hạn một phía, cần xét riêng giới hạn trái và phải, đặc biệt với hàm chứa trị tuyệt đối hoặc phân thức.",
    "complex": "Bài toán này thuộc dạng số phức. Số phức z = a + bi với i² = -1. Phép cộng/trừ: cộng/trừ phần thực và phần ảo riêng. Phép nhân: (a+bi)(c+di) = (ac-bd) + (ad+bc)i. Phép chia: nhân tử và mẫu cho số phức liên hợp. Mô-đun |z| = √(a²+b²), argument arg(z) = arctan(b/a).",
    "function": "Bài toán này thuộc dạng hàm số. Hàm số f: D → R ánh xạ mỗi x ∈ D sang một giá trị f(x) duy nhất. Hàm bậc nhất f(x) = ax + b có đồ thị đường thẳng. Hàm bậc hai f(x) = ax² + bx + c có đồ thị parabol. Để khảo sát hàm số, cần tìm tập xác định, đạo hàm, cực trị, tiệm cận.",
    "geometry_plane": "Bài toán này thuộc dạng hình học phẳng. Các hình cơ bản: tam giác (tổng ba góc = 180°, định lý Pythagoras cho tam giác vuông), tứ giác (hình vuông, chữ nhật, hình thang), đường tròn (chu vi = 2πr, diện tích = πr²). Các định lý quan trọng: Thales, Pitago, định lý cosin và sin trong tam giác.",
    "geometry_solid": "Bài toán này thuộc dạng hình học không gian. Công thức tính thể tích: hình hộp chữ nhật V = abc, hình lập phương V = a³, hình trụ V = πr²h, hình nón V = (1/3)πr²h, hình cầu V = (4/3)πr³, hình chóp V = (1/3)·S_đáy·h. Diện tích xung quanh: S_xq = chu vi đáy × chiều cao (cho trụ, hình nón cụt).",
    "algebra_basic": "Bài toán này thuộc dạng đại số cơ bản. Các quy tắc cần nhớ: phân phối a(b+c) = ab+ac, kết hợp (ab)c = a(bc), giao hoán ab = ba. Khi giải, cần đọc kỹ biểu thức, xác định thành phần, kiểm tra điều kiện, biến đổi từng bước và rút gọn về dạng chuẩn.",
    "linear_algebra": "Bài toán này thuộc đại số tuyến tính. Các khái niệm chính: không gian vectơ, ánh xạ tuyến tính, ma trận biểu diễn, hệ phương trình tuyến tính (giải bằng Gauss, Cramer), trị riêng và vectơ riêng (giải phương trình det(A - λI) = 0). Phép toán trên ma trận tuân theo các quy tắc đặc biệt (không giao hoán khi nhân).",
    "machine_learning": "Bài toán này thuộc lĩnh vực máy học. Quy trình chung: thu thập dữ liệu → tiền xử lý → trích chọn đặc trưng → chia tập train/val/test → chọn mô hình → huấn luyện → đánh giá → tinh chỉnh siêu tham số. Các thuật toán phổ biến: hồi quy tuyến tính/logistic, cây quyết định, SVM, k-NN, mạng nơ-ron.",
    "deep_learning": "Bài toán này thuộc lĩnh vực học sâu. Kiến trúc cơ bản: perceptron → MLP (nhiều lớp fully-connected) → CNN (tích chập cho ảnh) → RNN/LSTM/GRU (cho chuỗi) → Transformer (cho ngôn ngữ). Quá trình huấn luyện dùng gradient descent và lan truyền ngược (backpropagation). Hàm mất mát phổ biến: MSE (hồi quy), cross-entropy (phân loại).",
    "probability_stats": "Bài toán này thuộc dạng xác suất - thống kê. Xác suất P(A) = số trường hợp thuận lợi / tổng số trường hợp. Các công thức: P(A∪B) = P(A) + P(B) - P(A∩B), P(A∩B) = P(A)·P(B|A). Thống kê: kỳ vọng E(X), phương sai Var(X) = E(X²) - E(X)², độ lệch chuẩn σ = √Var(X).",
    "statistics": "Bài toán này thuộc dạng thống kê. Các đại lượng đặc trưng: trung bình μ = Σx_i/n, phương sai σ² = Σ(x_i - μ)²/n, độ lệch chuẩn σ = √σ². Các phân phối phổ biến: chuẩn N(μ, σ²), nhị thức B(n, p), Poisson P(λ), exponential Exp(λ).",
    "calculus": "Bài toán này thuộc giải tích. Giải tích nghiên cứu hàm số thông qua giới hạn, đạo hàm và tích phân. Đạo hàm biểu diễn tốc độ thay đổi tức thời. Tích phân biểu diễn tổng tích lũy hoặc diện tích dưới đường cong. Định lý cơ bản: ∫_a^b f'(x)dx = f(b) - f(a).",
    "factoring": "Bài toán này thuộc dạng phân tích đa thức thành nhân tử. Các phương pháp: đặt nhân tử chung, dùng hằng đẳng thức, nhóm hạng tử, tách hạng tử (cho đa thức bậc hai), phương pháp Euler. Mục đích: rút gọn biểu thức, giải phương trình bậc cao.",
    "math_general": "Bài toán này thuộc dạng toán tổng quát. Cần đọc kỹ đề bài, xác định dạng toán, áp dụng công thức phù hợp và thực hiện biến đổi một cách có hệ thống. Kết quả cần được rút gọn về dạng chuẩn.",
    "sequence": "Bài toán này thuộc dạng dãy số. Cấp số cộng có công thức u_n = u_1 + (n-1)d, tổng S_n = n(u_1 + u_n)/2. Cấp số nhân có công thức u_n = u_1·q^(n-1), tổng S_n = u_1(1-q^n)/(1-q) khi q ≠ 1.",
    "combinatorics": "Bài toán này thuộc dạng tổ hợp. Hoán vị P(n,k) = n!/(n-k)!. Chỉnh hợp A(n,k) = n!/(n-k)!. Tổ hợp C(n,k) = n!/(k!(n-k)!). Tam giác Pascal: C(n,k) = C(n-1,k-1) + C(n-1,k).",
    "optimization": "Bài toán này thuộc dạng tối ưu. Các phương pháp: gradient descent (cập nhật x ← x - α∇f), Newton method (dùng đạo hàm bậc hai), Lagrange multipliers (ràng buộc đẳng thức), KKT (ràng buộc bất đẳng thức).",
    "set_theory": "Bài toán này thuộc lý thuyết tập hợp. Phép toán: hợp A∪B, giao A∩B, hiệu A\\B, bù A^c. Các tính chất: giao hoán, kết hợp, phân phối, De Morgan: (A∪B)^c = A^c ∩ B^c.",
    "special_functions": "Bài toán này thuộc dạng hàm đặc biệt. Gamma function Γ(x) mở rộng giai thừa: Γ(n) = (n-1)!. Beta function B(x,y) liên quan tới tích phân elliptic. Hàm Bessel xuất hiện trong dao động và truyền sóng.",
    "data_structure_algorithm": "Bài toán này thuộc cấu trúc dữ liệu - giải thuật. Độ phức tạp thời gian O(n), O(n log n), O(n²), O(2^n). Cấu trúc dữ liệu: mảng, danh sách liên kết, ngăn xếp, hàng đợi, cây, đồ thị, bảng băm. Thuật toán: sắp xếp, tìm kiếm, duyệt đồ thị, quy hoạch động.",
    "information_systems": "Bài toán này thuộc hệ thống thông tin. Liên quan đến cơ sở dữ liệu, mạng, bảo mật, quản lý thông tin trong tổ chức.",
    "reinforcement_learning": "Bài toán này thuộc học tăng cường. Agent tương tác với môi trường, nhận reward và học policy tối ưu. Thuật toán: Q-learning, SARSA, Deep Q-Network (DQN), Policy Gradient, Actor-Critic.",
    "gaussian": "Bài toán này liên quan đến phân phối Gaussian (phân phối chuẩn). PDF: f(x) = (1/(σ√(2π)))·exp(-(x-μ)²/(2σ²)). Tính chất: đối xứng qua μ, 68-95-99.7 rule cho 1σ-2σ-3σ.",
    "definite_integral": "Bài toán này thuộc dạng tích phân xác định. Áp dụng công thức Newton-Leibniz: ∫_a^b f(x)dx = F(b) - F(a) với F là nguyên hàm của f.",
}


def get_reasoning(topic):
    """Lấy reasoning template cho topic."""
    return REASONING_BY_TOPIC.get(topic, REASONING_BY_TOPIC["math_general"])


# ============ MAIN TEMPLATE SELECTOR ============

def select_template(topic):
    """Trả về hàm template phù hợp với topic."""
    return TEMPLATES.get(topic, template_default)


def template_deep_learning(instruction, output):
    """Deep learning."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()
    if "softmax" in instr_lower:
        return [
            "Bước 1: Nhắc lại định nghĩa softmax: biến logits z thành xác suất p_i = exp(z_i)/Σexp(z_j).",
            "Bước 2: Áp dụng công thức softmax vào output và tính đạo hàm.",
            "Bước 3: Kết hợp với cross-entropy loss để có gradient đơn giản.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "gradient" in instr_lower or "đạo hàm" in instr_lower:
        return [
            "Bước 1: Xác định hàm mất mát cần tính gradient.",
            "Bước 2: Áp dụng quy tắc chain rule để lan truyền ngược qua các lớp.",
            "Bước 3: Tính gradient của từng tham số (trọng số, độ chệch).",
            "Bước 4: Rút gọn kết quả và trình bày dưới dạng vector gradient.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "convolution" in instr_lower or "tích chập" in instr_lower:
        return [
            "Bước 1: Xác định kích thước đầu vào W×H, kích thước kernel K×K.",
            "Bước 2: Áp dụng phép tích chập với stride S và padding P.",
            "Bước 3: Tính kích thước đầu ra theo công thức: (W - K + 2P)/S + 1.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "pooling" in instr_lower:
        return [
            "Bước 1: Xác định vùng pooling (max pooling hoặc average pooling).",
            "Bước 2: Chia đầu vào thành các vùng không giao nhau.",
            "Bước 3: Lấy giá trị lớn nhất (max) hoặc trung bình (average) của mỗi vùng.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "dropout" in instr_lower:
        return [
            "Bước 1: Trong quá trình huấn luyện, mỗi nơ-ron bị 'drop' với xác suất p.",
            "Bước 2: Forward pass: y = f(W·(M⊙x) + b), trong đó M là mặt nạ Bernoulli.",
            "Bước 3: Trong inference, không dropout, dùng toàn bộ nơ-ron.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "normalization" in instr_lower or "batch norm" in instr_lower:
        return [
            "Bước 1: Tính trung bình và phương sai của mỗi mini-batch.",
            "Bước 2: Chuẩn hóa: x_hat = (x - μ)/√(σ² + ε).",
            "Bước 3: Scale và shift: y = γ·x_hat + β.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "sgd" in instr_lower or "adam" in instr_lower or "optimizer" in instr_lower:
        return [
            "Bước 1: Tính gradient của hàm mất mát theo tham số hiện tại.",
            "Bước 2: Cập nhật tham số theo công thức optimizer: θ_{t+1} = θ_t - η·∇L.",
            "Bước 3: Với Adam/RMSprop, điều chỉnh learning rate thích ứng.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định kiến trúc mạng nơ-ron: số lớp, hàm kích hoạt, kích thước đầu vào/ra.",
        "Bước 2: Khởi tạo tham số (trọng số, độ chệch) với phương pháp phù hợp.",
        "Bước 3: Lan truyền tới: tính đầu ra qua từng lớp.",
        "Bước 4: Tính hàm mất mát và lan truyền ngược để cập nhật tham số.",
        f"Bước 5: Lặp lại qua nhiều epoch để hội tụ: $${out_clean}$$",
    ]


def template_machine_learning(instruction, output):
    """Machine learning cơ bản."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()
    if "regression" in instr_lower or "hồi quy" in instr_lower:
        return [
            "Bước 1: Xác định dạng mô hình hồi quy (tuyến tính, logistic, ridge, lasso).",
            "Bước 2: Xây dựng hàm mất mát: MSE cho hồi quy, log-loss cho phân loại.",
            "Bước 3: Tối ưu tham số bằng gradient descent hoặc phương trình chuẩn.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "classification" in instr_lower or "phân loại" in instr_lower:
        return [
            "Bước 1: Chọn thuật toán phân loại (k-NN, SVM, cây quyết định, mạng nơ-ron).",
            "Bước 2: Trích chọn đặc trưng và chia tập train/val/test.",
            "Bước 3: Huấn luyện mô hình trên tập train.",
            "Bước 4: Đánh giá trên tập val/test bằng accuracy, precision, recall.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    if "pca" in instr_lower or "giảm chiều" in instr_lower:
        return [
            "Bước 1: Chuẩn hóa dữ liệu về trung bình 0.",
            "Bước 2: Tính ma trận hiệp phương sai.",
            "Bước 3: Tìm trị riêng và vectơ riêng.",
            "Bước 4: Chọn k thành phần chính (trị riêng lớn nhất).",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Thu thập và tiền xử lý dữ liệu.",
        "Bước 2: Chia tập dữ liệu: train/validation/test.",
        "Bước 3: Chọn mô hình máy học phù hợp.",
        "Bước 4: Huấn luyện mô hình trên tập train.",
        "Bước 5: Đánh giá và tinh chỉnh siêu tham số.",
        f"Bước 6: Trình bày đáp án: $${out_clean}$$",
    ]


def template_optimization(instruction, output):
    """Tối ưu."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()
    if "lagrange" in instr_lower:
        return [
            "Bước 1: Xác định hàm mục tiêu f(x) và ràng buộc g(x) = 0.",
            "Bước 2: Lập hàm Lagrange: L(x, λ) = f(x) + λ·g(x).",
            "Bước 3: Tính đạo hàm riêng và giải hệ phương trình: ∇f + λ∇g = 0, g(x) = 0.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "gradient descent" in instr_lower:
        return [
            "Bước 1: Khởi tạo tham số θ₀ ngẫu nhiên.",
            "Bước 2: Tính gradient ∇L(θ_t) của hàm mất mát.",
            "Bước 3: Cập nhật tham số: θ_{t+1} = θ_t - α·∇L(θ_t).",
            "Bước 4: Lặp lại cho đến khi hội tụ.",
            f"Bước 5: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định bài toán tối ưu: hàm mục tiêu, biến số, ràng buộc.",
        "Bước 2: Chọn phương pháp tối ưu phù hợp (gradient descent, Newton, Lagrange).",
        "Bước 3: Thiết lập điều kiện tối ưu (đạo hàm = 0, KKT).",
        "Bước 4: Giải hệ phương trình tối ưu.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_linear_algebra(instruction, output):
    """Đại số tuyến tính."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()
    if "trị riêng" in instr_lower or "eigenvalue" in instr_lower:
        return [
            "Bước 1: Lập phương trình đặc trưng: det(A - λI) = 0.",
            "Bước 2: Tính định thức và giải phương trình bậc n tìm λ.",
            "Bước 3: Với mỗi λ, giải (A - λI)v = 0 để tìm vectơ riêng v.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "vectơ riêng" in instr_lower or "eigenvector" in instr_lower:
        return [
            "Bước 1: Tìm trị riêng λ từ phương trình det(A - λI) = 0.",
            "Bước 2: Với mỗi λ, giải hệ (A - λI)v = 0.",
            "Bước 3: Tìm không gian nghiệm (vectơ riêng ứng với λ).",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "định thức" in instr_lower or "determinant" in instr_lower:
        return [
            "Bước 1: Kiểm tra ma trận vuông.",
            "Bước 2: Áp dụng công thức định thức (cấp 2: ad-bc, cấp 3: Sarrus, cấp n: khai triển).",
            "Bước 3: Tính từng phần tử.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "ma trận nghịch đảo" in instr_lower or "inverse" in instr_lower:
        return [
            "Bước 1: Tính định thức det(A), kiểm tra det(A) ≠ 0.",
            "Bước 2: Tìm ma trận phụ hợp adj(A).",
            "Bước 3: Tính A^(-1) = adj(A) / det(A).",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "hệ phương trình" in instr_lower or "hệ tuyến tính" in instr_lower:
        return [
            "Bước 1: Viết ma trận mở rộng [A|b] của hệ Ax = b.",
            "Bước 2: Áp dụng phép khử Gauss để đưa về dạng bậc thang.",
            "Bước 3: Thế ngược tìm nghiệm.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định đối tượng đại số tuyến tính (ma trận, vectơ, ánh xạ).",
        "Bước 2: Áp dụng tính chất/phép toán phù hợp.",
        "Bước 3: Tính toán từng bước.",
        f"Bước 4: Trình bày đáp án: $${out_clean}$$",
    ]


def template_set_theory(instruction, output):
    """Lý thuyết tập hợp."""
    out_clean = _clean_output_latex(output)
    return [
        "Bước 1: Xác định các tập hợp liên quan và phép toán cần thực hiện.",
        "Bước 2: Áp dụng phép toán tập hợp (hợp ∪, giao ∩, hiệu \\, bù ᶜ).",
        "Bước 3: Tính kết quả và biểu diễn bằng ký hiệu tập hợp.",
        f"Bước 4: Trình bày đáp án: $${out_clean}$$",
    ]


def template_special_functions(instruction, output):
    """Hàm đặc biệt (Gamma, Bessel, ...)."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()
    if "gamma" in instr_lower:
        return [
            "Bước 1: Nhắc lại định nghĩa hàm Gamma: Γ(x) = ∫_0^∞ t^(x-1) e^(-t) dt.",
            "Bước 2: Áp dụng tính chất Γ(x+1) = x·Γ(x), Γ(n) = (n-1)!.",
            "Bước 3: Sử dụng để tính giá trị cụ thể.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "bessel" in instr_lower:
        return [
            "Bước 1: Nhắc lại phương trình Bessel: x²y'' + xy' + (x² - ν²)y = 0.",
            "Bước 2: Nghiệm tổng quát: y = c₁·J_ν(x) + c₂·Y_ν(x).",
            "Bước 3: Xác định bậc ν từ điều kiện bài toán.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Nhắc lại định nghĩa và tính chất của hàm đặc biệt đang xét.",
        "Bước 2: Áp dụng công thức và quan hệ đặc trưng.",
        "Bước 3: Tính toán giá trị cụ thể.",
        f"Bước 4: Trình bày đáp án: $${out_clean}$$",
    ]


def template_data_structure_algorithm(instruction, output):
    """Cấu trúc dữ liệu - Giải thuật."""
    out_clean = _clean_output_latex(output)
    return [
        "Bước 1: Xác định cấu trúc dữ liệu hoặc thuật toán cần phân tích.",
        "Bước 2: Phân tích độ phức tạp thời gian O(...) và bộ nhớ.",
        "Bước 3: Áp dụng thuật toán vào bài toán cụ thể.",
        "Bước 4: Đánh giá tính đúng đắn và hiệu quả.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_information_systems(instruction, output):
    """Hệ thống thông tin."""
    out_clean = _clean_output_latex(output)
    return [
        "Bước 1: Phân tích yêu cầu hệ thống thông tin.",
        "Bước 2: Thiết kế cơ sở dữ liệu và kiến trúc hệ thống.",
        "Bước 3: Triển khai và kiểm thử.",
        f"Bước 4: Trình bày đáp án: $${out_clean}$$",
    ]


def template_statistics(instruction, output):
    """Thống kê."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()
    if "kỳ vọng" in instr_lower or "expectation" in instr_lower:
        return [
            "Bước 1: Xác định phân phối của biến ngẫu nhiên X.",
            "Bước 2: Áp dụng công thức kỳ vọng: E(X) = Σx·P(x) hoặc ∫x·f(x)dx.",
            "Bước 3: Tính toán giá trị.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "phương sai" in instr_lower or "variance" in instr_lower:
        return [
            "Bước 1: Tính kỳ vọng E(X).",
            "Bước 2: Áp dụng Var(X) = E(X²) - [E(X)]².",
            "Bước 3: Tính toán cụ thể.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định dữ liệu và phân phối.",
        "Bước 2: Tính các đại lượng thống kê (trung bình, phương sai, ...).",
        "Bước 3: Phân tích và rút ra kết luận.",
        f"Bước 4: Trình bày đáp án: $${out_clean}$$",
    ]


def template_probability(instruction, output):
    """Xác suất."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()
    if "poisson" in instr_lower:
        return [
            "Bước 1: Xác định phân phối Poisson với tham số λ.",
            "Bước 2: Áp dụng công thức P(X=k) = (λ^k·e^(-λ))/k!.",
            "Bước 3: Tính giá trị cụ thể cho k cụ thể.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "bernoulli" in instr_lower:
        return [
            "Bước 1: Xác định phân phối Bernoulli với xác suất thành công p.",
            "Bước 2: Áp dụng công thức: P(X=1) = p, P(X=0) = 1-p.",
            "Bước 3: Tính kỳ vọng E(X) = p, phương sai Var(X) = p(1-p).",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định không gian mẫu và biến cố.",
        "Bước 2: Áp dụng công thức xác suất phù hợp.",
        "Bước 3: Tính xác suất và rút ra kết luận.",
        f"Bước 4: Trình bày đáp án: $${out_clean}$$",
    ]


def template_probability_stats(instruction, output):
    """Xác suất - Thống kê."""
    return template_probability(instruction, output)


def template_sequence(instruction, output):
    """Dãy số, chuỗi."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()
    if "cấp số cộng" in instr_lower:
        return [
            "Bước 1: Xác định số hạng đầu u₁ và công sai d.",
            "Bước 2: Áp dụng công thức số hạng tổng quát: uₙ = u₁ + (n-1)d.",
            "Bước 3: Tính tổng n số hạng: Sₙ = n(u₁ + uₙ)/2.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "cấp số nhân" in instr_lower:
        return [
            "Bước 1: Xác định số hạng đầu u₁ và công bội q.",
            "Bước 2: Áp dụng công thức số hạng tổng quát: uₙ = u₁·q^(n-1).",
            "Bước 3: Tính tổng n số hạng: Sₙ = u₁(1-q^n)/(1-q) khi q≠1.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định dạng dãy số và quy luật.",
        "Bước 2: Áp dụng công thức phù hợp.",
        "Bước 3: Tính số hạng tổng quát và tổng.",
        f"Bước 4: Trình bày đáp án: $${out_clean}$$",
    ]


def template_combinatorics(instruction, output):
    """Tổ hợp."""
    out_clean = _clean_output_latex(output)
    instr_lower = instruction.lower()
    if "hoán vị" in instr_lower:
        return [
            "Bước 1: Xác định số phần tử n và số phần tử cần chọn k.",
            "Bước 2: Áp dụng công thức hoán vị: P(n,k) = n!/(n-k)!.",
            "Bước 3: Tính toán cụ thể.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    if "chỉnh hợp" in instr_lower:
        return [
            "Bước 1: Xác định n và k.",
            "Bước 2: Áp dụng A(n,k) = n!/(n-k)!.",
            "Bước 3: Tính giá trị.",
            f"Bước 4: Trình bày đáp án: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định loại bài toán tổ hợp (hoán vị, chỉnh hợp, tổ hợp).",
        "Bước 2: Xác định n và k.",
        "Bước 3: Áp dụng công thức tương ứng.",
        f"Bước 4: Trình bày đáp án: $${out_clean}$$",
    ]


def template_factoring(instruction, output):
    """Phân tích nhân tử."""
    out_clean = _clean_output_latex(output)
    return [
        "Bước 1: Kiểm tra có nhân tử chung không.",
        "Bước 2: Áp dụng hằng đẳng thức nếu có.",
        "Bước 3: Nhóm hạng tử hoặc tách hạng tử (nếu cần).",
        "Bước 4: Phân tích đa thức thành tích các đa thức bậc thấp hơn.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


def template_polynomial(instruction, output):
    """Đa thức."""
    out_clean = _clean_output_latex(output)
    if "định nghĩa" in instruction.lower() or "tổng quát" in instruction.lower():
        return [
            "Bước 1: Nhắc lại định nghĩa đa thức bậc n: P(x) = a_n x^n + ... + a_1 x + a_0.",
            "Bước 2: Liệt kê các hệ số a_n, a_{n-1}, ..., a_0 và bậc n.",
            "Bước 3: Trình bày dạng tổng quát của đa thức.",
            f"Bước 4: Kết luận: $${out_clean}$$",
        ]
    return [
        "Bước 1: Xác định bậc và hệ số của đa thức.",
        "Bước 2: Áp dụng phép toán đa thức phù hợp (cộng, trừ, nhân, chia, phân tích).",
        "Bước 3: Thực hiện biến đổi từng bước.",
        "Bước 4: Rút gọn về dạng chuẩn.",
        f"Bước 5: Trình bày đáp án: $${out_clean}$$",
    ]


TEMPLATES = {
    "equation": template_equation,
    "derivative": template_derivative,
    "integral": template_integral,
    "trigonometric": template_trigonometric,
    "exponential": template_exponential,
    "logarithm": template_logarithm,
    "matrix": template_matrix,
    "vector": template_vector,
    "polynomial": template_polynomial,
    "limit": template_limit,
    "complex": template_complex,
    "function": template_function,
    "geometry_plane": template_geometry_plane,
    "geometry_solid": template_geometry_solid,
    "algebra_basic": template_algebra_basic,
    "deep_learning": template_deep_learning,
    "machine_learning": template_machine_learning,
    "optimization": template_optimization,
    "linear_algebra": template_linear_algebra,
    "set_theory": template_set_theory,
    "special_functions": template_special_functions,
    "data_structure_algorithm": template_data_structure_algorithm,
    "information_systems": template_information_systems,
    "statistics": template_statistics,
    "probability": template_probability,
    "probability_stats": template_probability_stats,
    "sequence": template_sequence,
    "combinatorics": template_combinatorics,
    "factoring": template_factoring,
    "polynomial": template_polynomial,
}


if __name__ == "__main__":
    # Test
    print("=== TEST TEMPLATES ===\n")
    test_cases = [
        ("fraction", "Trừ hai phân số cùng mẫu", "x - y = \\frac{a - b}{m}"),
        ("equation", "Phương trình mũ cơ bản", "m^x = n \\khi và chỉ khi x = \\log_m n"),
        ("derivative", "Tính đạo hàm của hàm hợp (Quy tắc hàm hợp)", "(f(g(x)))' = f'(g(x)) \\cdot g'(x)"),
        ("integral", "Định nghĩa hàm Gamma (Hàm giải thừa mở rộng)", "f(x) = \\int_{0}^{\\infty} y^{x-1} e^{-y} dy"),
        ("trigonometric", "Hệ thức lượng giác cơ bản (Định lý Pythagoras trong lượng giác)", "\\sin^2 x + \\cos^2 x = 1"),
        ("matrix", "Ma trận kề", "A_{ij} = 1 \\text{ nếu có cạnh}"),
        ("geometry_solid", "Thể tích hình nón", "V = \\frac{1}{3} \\pi r^2 h"),
    ]

    for topic, instr, output in test_cases:
        print(f"\n--- Topic: {topic} ---")
        print(f"Instruction: {instr}")
        print(f"Output: {output}")
        tmpl = select_template(topic)
        steps = tmpl(instr, output)
        print("Steps:")
        for s in steps:
            print(f"  {s}")
        print(f"Reasoning: {get_reasoning(topic)[:200]}...")