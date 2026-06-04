import json
import math
import re
from fractions import Fraction
from pathlib import Path


DATA_PATH = Path("formulas/datasheet.json")


def as_text(value):
    return value if isinstance(value, str) else ""


def item_formula(item):
    return (
        as_text(item.get("output"))
        or as_text(item.get("canonical_form"))
        or as_text(item.get("input"))
    ).strip()


def compact_formula(text, limit=100):
    value = " ".join(as_text(text).split())
    return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."


def norm_text(item):
    parts = [
        item.get("id", ""),
        item.get("instruction", ""),
        item.get("input", ""),
        item.get("output", ""),
        item.get("canonical_form", ""),
        " ".join(item.get("tags") or []),
        item.get("type", ""),
    ]
    return " ".join(as_text(x) for x in parts).lower()


def primary_text(item):
    parts = [
        item.get("id", ""),
        item.get("instruction", ""),
        item.get("input", ""),
        item.get("output", ""),
        item.get("canonical_form", ""),
    ]
    return " ".join(as_text(x) for x in parts).lower()


def has_any(text, terms):
    return any(term in text for term in terms)


def has_probability_evidence(item):
    raw_text = " ".join(
        as_text(x)
        for x in [
            item.get("id", ""),
            item.get("instruction", ""),
            item.get("input", ""),
            item.get("output", ""),
            item.get("canonical_form", ""),
        ]
    )
    text = raw_text.lower()
    terms = [
        "xác suất",
        "xac suat",
        "bayes",
        "kỳ vọng",
        "ky vong",
        "phương sai",
        "phuong sai",
        "hiệp phương sai",
        "hiep phuong sai",
        "tương quan",
        "tuong quan",
        "phân phối",
        "phan phoi",
        "entropy",
        "likelihood",
        "posterior",
        "gaussian",
        "poisson",
        "binomial",
        "nhị thức",
        "nhi thuc",
        "\\mathbb{p}",
        "\\mathbb{e}",
        "var(",
        "cov(",
        "logistic",
        "naive bayes",
        "gmm",
        "collision",
        "birthday",
    ]
    if has_any(text, terms):
        return True
    return bool(re.search(r"(?<![\w\\])p\s*(?:\\left\s*)?\(", raw_text, flags=re.IGNORECASE))


def classify(item):
    text = norm_text(item)
    tags = set(item.get("tags") or [])
    item_type = item.get("type")
    formula = item_formula(item).lower()

    crypto_terms = [
        "rsa",
        "diffie",
        "khóa",
        "khoa",
        "mã hóa",
        "ma hoa",
        "giải mã",
        "giai ma",
        "modulus",
        "totient",
        "log rời rạc",
        "log roi rac",
        "modulo",
        "pmod",
        "băm",
        "hash",
        "bảng băm",
        "bang bam",
    ]
    if has_any(text, crypto_terms) and not has_any(primary_text(item), ["birthday", "collision", "va chạm", "va cham", "xác suất", "xac suat"]):
        return "number_theory_crypto"

    if item_type == "combinatorics" or "combinatorics" in tags or "tổ hợp" in text:
        return "combinatorics"

    if ("fraction" in tags or "phân số" in text or "phan so" in text) and not has_any(text, ["xác suất", "probability"]):
        return "fraction"

    if "\\int" in formula or "integral" in tags or "tích phân" in text:
        return "integral"
    if "\\lim" in formula or "limit" in tags or "giới hạn" in text:
        return "limit"
    if "\\frac{d" in formula or "\\partial" in formula or "derivative" in tags or "đạo hàm" in text:
        return "derivative"

    if item_type == "deep_learning" or "deep_learning" in tags:
        return "deep_learning"
    if item_type == "optimization" or "optimization" in tags:
        return "optimization"
    if item_type == "machine_learning" or "machine_learning" in tags or "loss_function" in tags or "cross-entropy" in text or "cross entropy" in text:
        return "machine_learning"
    if item_type == "linear_algebra" or "linear_algebra" in tags or "matrix" in tags:
        return "linear_algebra"
    if item_type == "trigonometry" or "trigonometry" in tags:
        return "trigonometry"
    if item_type == "geometry" or "geometry" in tags:
        return "geometry"

    if "\\log" in formula or "logarithm" in tags:
        return "logarithm"
    if "\\sqrt" in formula or "radical" in tags:
        return "radical"
    if "^" in formula or "exponent" in tags:
        return "exponent"

    if has_probability_evidence(item):
        return "probability"

    if item_type == "statistics" or "statistics" in tags:
        return "statistics"
    if item_type == "sequences" or "sequence" in tags or "dãy" in text:
        return "sequences"
    if item_type == "mathematical_physics" or "special_function" in tags:
        return "special_function"

    if item_type == "calculus" or "calculus" in tags:
        return "calculus"
    return "algebra"


def build_steps(item, topic):
    instruction = as_text(item.get("instruction")).strip() or "bài toán"
    formula = compact_formula(item_formula(item))
    constraints = item.get("constraints") or []
    constraint_text = "; ".join(str(x) for x in constraints[:2]) if constraints else "các điều kiện miền xác định của công thức"

    if topic == "fraction":
        text = norm_text(item)
        if "cùng mẫu" in text:
            return [
                "Xác định hai phân số cùng mẫu và kiểm tra mẫu số khác 0.",
                "Giữ nguyên mẫu chung vì hai phân số đã cùng mẫu.",
                "Thực hiện phép toán trên tử số theo đúng dấu của đề bài.",
                "Rút gọn tử số và phân số thu được nếu có ước chung.",
                "Viết kết quả cuối cùng bằng LaTeX chuẩn, không đảo nhầm tử và mẫu.",
            ]
        if "khác mẫu" in text:
            return [
                "Xác định tử số và mẫu số của từng phân số, đồng thời kiểm tra các mẫu khác 0.",
                "Chọn mẫu số chung, thường dùng tích hai mẫu hoặc bội chung nhỏ nhất nếu cần rút gọn.",
                "Quy đồng từng phân số bằng cách nhân cả tử và mẫu với cùng một thừa số.",
                "Cộng hoặc trừ các tử số sau khi đã cùng mẫu, rồi giữ nguyên mẫu chung.",
                "Rút gọn phân số và viết đáp án cuối cùng đúng cú pháp LaTeX.",
            ]
        if "nhân" in text:
            return [
                "Xác định tử số và mẫu số của từng phân số, đồng thời kiểm tra các mẫu khác 0.",
                "Nhân tử số với tử số để tạo tử số mới.",
                "Nhân mẫu số với mẫu số để tạo mẫu số mới.",
                "Rút gọn các thừa số chung trước hoặc sau khi nhân nếu có thể.",
                "Viết tích cuối cùng dưới dạng phân số LaTeX chuẩn.",
            ]
        if "chia" in text or "nghịch đảo" in text:
            return [
                "Xác định phân số bị chia và phân số chia, đồng thời kiểm tra phân số chia khác 0.",
                "Đảo ngược phân số chia để chuyển phép chia thành phép nhân.",
                "Nhân tử với tử và mẫu với mẫu theo quy tắc nhân phân số.",
                "Rút gọn các thừa số chung nếu có.",
                "Viết thương cuối cùng dưới dạng LaTeX chuẩn.",
            ]
        return [
            "Xác định rõ tử số, mẫu số và điều kiện mẫu số khác 0.",
            "Áp dụng đúng quy tắc phân số tương ứng với yêu cầu của bài.",
            "Thay số vào đúng vị trí tử hoặc mẫu, không tráo vai trò của các biến.",
            "Rút gọn phân số nếu tử và mẫu có ước chung.",
            "Viết kết quả cuối cùng bằng LaTeX chuẩn.",
        ]

    if topic == "probability":
        text = norm_text(item)
        if "bayes" in text:
            return [
                "Xác định biến cố giả thuyết, biến cố quan sát và các xác suất đã biết.",
                "Tách rõ prior, likelihood và evidence trong công thức Bayes.",
                "Kiểm tra mẫu số hoặc xác suất điều kiện ở mẫu phải lớn hơn 0.",
                "Thay các xác suất vào đúng vị trí tử số và mẫu số, rồi tính giá trị hậu nghiệm.",
                "Kiểm tra kết quả nằm trong khoảng từ 0 đến 1 và viết bằng LaTeX chuẩn.",
            ]
        if "có điều kiện" in text or "conditional" in text or "\\mid" in text or "|" in item_formula(item):
            return [
                "Xác định biến cố cần tính và biến cố điều kiện.",
                "Tìm xác suất giao của hai biến cố và xác suất của biến cố điều kiện.",
                "Kiểm tra xác suất của biến cố điều kiện khác 0.",
                "Lấy xác suất giao chia cho xác suất điều kiện theo định nghĩa xác suất có điều kiện.",
                "Rút gọn kết quả và kiểm tra giá trị thu được nằm trong khoảng từ 0 đến 1.",
            ]
        if "\\cup" in item_formula(item) or "hợp xác suất" in text:
            return [
                "Xác định hai biến cố cần lấy hợp và các xác suất riêng lẻ của chúng.",
                "Xác định phần giao bị đếm trùng khi cộng hai xác suất riêng.",
                "Áp dụng công thức cộng xác suất \\(P(A\\cup B)=P(A)+P(B)-P(A\\cap B)\\).",
                "Thay các giá trị vào đúng vị trí và thực hiện phép cộng trừ.",
                "Kiểm tra kết quả nằm trong khoảng từ 0 đến 1 và viết bằng LaTeX chuẩn.",
            ]
        if "\\cap" in item_formula(item) or "xác suất giao" in text or "độc lập" in text:
            return [
                "Xác định hai biến cố cần lấy giao và quan hệ giữa chúng.",
                "Nếu có điều kiện, dùng quy tắc nhân \\(P(A\\cap B)=P(A\\mid B)P(B)\\) hoặc dạng tương đương.",
                "Nếu hai biến cố độc lập, thay bằng tích \\(P(A)P(B)\\).",
                "Thay các xác suất vào đúng vị trí và nhân các giá trị tương ứng.",
                "Kiểm tra kết quả nằm trong khoảng từ 0 đến 1 và viết bằng LaTeX chuẩn.",
            ]
        if "phân phối" in text or "distribution" in text or "poisson" in text or "binomial" in text or "gaussian" in text:
            return [
                "Xác định loại phân phối và các tham số của phân phối.",
                "Kiểm tra điều kiện của tham số, ví dụ xác suất thuộc [0,1], phương sai dương hoặc chỉ số là số nguyên không âm.",
                "Thay đúng giá trị của biến ngẫu nhiên và tham số vào pmf hoặc pdf.",
                "Tính các thành phần như hệ số tổ hợp, lũy thừa, hàm mũ hoặc hệ số chuẩn hóa.",
                "Viết xác suất hoặc mật độ cuối cùng bằng LaTeX chuẩn và kiểm tra kết quả không âm.",
            ]
        if "kỳ vọng" in text or "ky vong" in text or "\\mathbb{e}" in text:
            return [
                "Xác định biến ngẫu nhiên và bảng giá trị hoặc hàm mật độ/xác suất của nó.",
                "Chọn dạng tổng cho biến rời rạc hoặc dạng tích phân cho biến liên tục.",
                "Nhân từng giá trị của biến với xác suất hoặc mật độ tương ứng.",
                "Cộng hoặc tích phân trên toàn bộ miền xác định.",
                "Viết kỳ vọng cuối cùng bằng LaTeX chuẩn kèm điều kiện hội tụ nếu cần.",
            ]
        if "phương sai" in text or "variance" in text or "var(" in text:
            return [
                "Xác định biến ngẫu nhiên và kỳ vọng của biến đó.",
                "Tính hoặc thay giá trị của moment bậc hai \\(E[X^2]\\).",
                "Áp dụng công thức phương sai \\(Var(X)=E[X^2]-E[X]^2\\) hoặc dạng tương đương.",
                "Kiểm tra phương sai không âm và các tham số như độ lệch chuẩn khác 0 nếu có chia.",
                "Viết kết quả cuối cùng bằng LaTeX chuẩn.",
            ]
        if "cov" in text or "hiệp phương sai" in text or "tương quan" in text:
            return [
                "Xác định hai biến ngẫu nhiên và các kỳ vọng liên quan.",
                "Tính kỳ vọng tích hoặc hiệp phương sai theo định nghĩa.",
                "Nếu tính tương quan, chia hiệp phương sai cho tích hai độ lệch chuẩn.",
                "Kiểm tra các độ lệch chuẩn ở mẫu số khác 0.",
                "Viết kết quả cuối cùng bằng LaTeX chuẩn và nêu ý nghĩa quan hệ giữa hai biến nếu cần.",
            ]
        if "likelihood" in text or "mle" in text or "map" in text:
            return [
                "Xác định dữ liệu quan sát, tham số cần ước lượng và mô hình xác suất.",
                "Lập likelihood hoặc log-likelihood từ tích/xuất hiện của các xác suất quan sát.",
                "Với MAP, nhân thêm prior hoặc cộng log-prior vào log-likelihood.",
                "Tối ưu biểu thức theo tham số bằng argmax hoặc điều kiện đạo hàm nếu cần.",
                "Viết ước lượng cuối cùng bằng LaTeX chuẩn và giữ đúng chỉ số mẫu.",
            ]
        return [
            "Xác định không gian mẫu, biến cố hoặc biến ngẫu nhiên xuất hiện trong bài.",
            "Chọn đúng quy tắc xác suất cần áp dụng: cộng, nhân, điều kiện, kỳ vọng hoặc phân phối.",
            "Kiểm tra điều kiện hợp lệ của xác suất và mẫu số nếu có phép chia.",
            "Thay các giá trị đã biết vào đúng vị trí của công thức.",
            "Tính và viết kết quả bằng LaTeX chuẩn, bảo đảm xác suất nằm trong khoảng từ 0 đến 1 khi áp dụng.",
        ]

    template_map = {
        "number_theory_crypto": [
            "Xác định các số nguyên, khóa, modulus hoặc tham số modulo trong bài.",
            "Kiểm tra điều kiện số học cần thiết, ví dụ modulus dương, số nguyên tố hoặc tính đồng dư.",
            "Thay giá trị vào đúng vị trí của công thức số học modulo.",
            "Thực hiện nhân, lũy thừa hoặc rút gọn theo modulus tương ứng.",
            "Viết kết quả cuối cùng bằng LaTeX chuẩn và giữ đúng ký hiệu \\(\\bmod\\) hoặc \\(\\pmod{}\\).",
        ],
        "combinatorics": [
            "Xác định tổng số phần tử \\(n\\) và số phần tử được chọn \\(r\\) hoặc \\(k\\).",
            "Kiểm tra điều kiện \\(0 \\le r \\le n\\) và các đại lượng là số nguyên không âm.",
            "Áp dụng công thức tổ hợp hoặc hoán vị tương ứng với việc có xét thứ tự hay không.",
            "Thay số vào giai thừa hoặc hệ số nhị thức rồi rút gọn.",
            "Viết kết quả cuối cùng bằng LaTeX chuẩn và không nhầm với quy tắc xác suất.",
        ],
        "statistics": [
            "Xác định mẫu dữ liệu, biến thống kê và các tham số như trung bình, phương sai hoặc kích thước mẫu.",
            "Kiểm tra điều kiện dữ liệu hợp lệ và mẫu số khác 0 nếu công thức có phép chia.",
            "Thay các giá trị vào đúng vị trí của công thức thống kê.",
            "Thực hiện tổng, bình phương, căn hoặc chuẩn hóa theo đúng thứ tự.",
            "Viết kết quả bằng LaTeX chuẩn và diễn giải đúng đại lượng thống kê đang tính.",
        ],
        "integral": [
            "Nhận dạng hàm dưới dấu tích phân, biến tích phân và các tham số đi kèm.",
            "Kiểm tra miền xác định và điều kiện hội tụ nếu là tích phân suy rộng hoặc tích phân xác định.",
            "Chọn công thức nguyên hàm, đổi biến hoặc tích phân từng phần phù hợp.",
            "Thay đúng tham số vào công thức và giữ nguyên biến vi phân.",
            "Viết kết quả bằng LaTeX chuẩn, thêm hằng số \\(C\\) cho tích phân bất định nếu cần.",
        ],
        "derivative": [
            "Xác định hàm cần lấy đạo hàm, biến đạo hàm và các tham số cố định.",
            "Kiểm tra miền xác định của hàm và các biểu thức trong căn, logarit hoặc mẫu số.",
            "Chọn quy tắc đạo hàm phù hợp: dây chuyền, tích, thương, hàm ngược hoặc đạo hàm riêng.",
            "Thực hiện đạo hàm theo đúng biến, không thay biến vi phân thành số.",
            "Rút gọn và viết kết quả đạo hàm bằng LaTeX chuẩn.",
        ],
        "limit": [
            "Xác định điểm tiến tới, phía tiến tới nếu có và biểu thức cần lấy giới hạn.",
            "Kiểm tra dạng vô định hoặc điều kiện tồn tại của giới hạn.",
            "Tính giới hạn trái, phải hoặc biến đổi biểu thức bằng quy tắc phù hợp.",
            "So sánh các giới hạn một phía nếu bài yêu cầu xét tồn tại.",
            "Kết luận giới hạn bằng LaTeX chuẩn, nêu rõ nếu giới hạn không tồn tại.",
        ],
        "calculus": [
            "Xác định đối tượng giải tích cần xử lý: hàm số, biến, điểm xét hoặc tham số.",
            "Kiểm tra miền xác định và điều kiện khả vi/liên tục/hội tụ phù hợp.",
            "Chọn định nghĩa hoặc định lý giải tích đúng với công thức.",
            "Thay dữ kiện vào công thức mà không thay nhầm biến bị ràng buộc.",
            "Rút gọn và viết kết quả cuối cùng bằng LaTeX chuẩn.",
        ],
        "linear_algebra": [
            "Xác định vector, ma trận, kích thước và phép toán đại số tuyến tính cần dùng.",
            "Kiểm tra điều kiện tương thích kích thước, khả nghịch hoặc chuẩn khác 0 nếu có chia.",
            "Áp dụng đúng quy tắc nhân ma trận, chuyển vị, định thức, trị riêng hoặc gradient.",
            "Thay dữ kiện vào công thức và giữ đúng thứ tự nhân ma trận.",
            "Viết kết quả bằng LaTeX chuẩn với kích thước đầu ra phù hợp.",
        ],
        "optimization": [
            "Xác định hàm mục tiêu, biến tối ưu và các ràng buộc nếu có.",
            "Tính gradient, đạo hàm riêng hoặc điều kiện tối ưu cần thiết.",
            "Áp dụng đúng quy tắc cập nhật hoặc điều kiện cực trị theo bài toán.",
            "Kiểm tra dấu của bước cập nhật, hệ số học và điều kiện hội tụ.",
            "Viết nghiệm hoặc công thức cập nhật cuối cùng bằng LaTeX chuẩn.",
        ],
        "machine_learning": [
            "Xác định đầu vào, nhãn, tham số mô hình và đại lượng cần tính.",
            "Kiểm tra kích thước vector/ma trận hoặc điều kiện xác suất nếu công thức có phân phối.",
            "Thay đúng tensor, vector hoặc tham số vào công thức mô hình.",
            "Thực hiện phép tính đặc trưng như loss, gradient, likelihood hoặc dự đoán.",
            "Viết kết quả bằng LaTeX chuẩn và giữ đúng vai trò của dữ liệu, nhãn và tham số.",
        ],
        "deep_learning": [
            "Xác định tensor đầu vào, trọng số, bias, kích thước batch hoặc chiều đặc trưng.",
            "Kiểm tra điều kiện kích thước để phép nhân, attention, normalization hoặc convolution hợp lệ.",
            "Áp dụng đúng công thức forward, loss, gradient hoặc cập nhật trạng thái.",
            "Thay các tham số vào đúng vị trí, không đổi chỉ số hoặc chiều tensor thành giá trị sai.",
            "Viết biểu thức cuối cùng bằng LaTeX chuẩn với shape đầu ra phù hợp.",
        ],
        "trigonometry": [
            "Xác định góc và các hàm lượng giác xuất hiện trong công thức.",
            "Kiểm tra điều kiện mẫu số khác 0 đối với tan, cot, sec hoặc csc.",
            "Chọn đúng hằng đẳng thức: Pythagoras, cộng góc, nhân đôi, hạ bậc hoặc hệ thức tam giác.",
            "Thay góc vào đúng vị trí và giữ nhất quán đơn vị radian/độ.",
            "Rút gọn và viết kết quả bằng LaTeX chuẩn.",
        ],
        "geometry": [
            "Xác định hình học, các đại lượng đã biết và đại lượng cần tính.",
            "Kiểm tra điều kiện hình học như độ dài dương, góc hợp lệ hoặc điểm/đường thuộc miền xét.",
            "Chọn đúng công thức diện tích, thể tích, khoảng cách, góc hoặc phương trình hình học.",
            "Thay số vào đúng vị trí của cạnh, bán kính, chiều cao, tọa độ hoặc góc.",
            "Rút gọn và viết kết quả cuối cùng bằng LaTeX chuẩn.",
        ],
        "sequences": [
            "Xác định loại dãy, số hạng đầu, công sai/công bội và vị trí cần tính.",
            "Kiểm tra điều kiện chỉ số là số nguyên dương và tham số phù hợp.",
            "Chọn công thức số hạng tổng quát hoặc tổng hữu hạn tương ứng.",
            "Thay dữ kiện vào đúng vị trí của chỉ số và tham số.",
            "Rút gọn và viết kết quả bằng LaTeX chuẩn.",
        ],
        "special_function": [
            "Xác định hàm đặc biệt, bậc/order, biến và tham số xuất hiện trong công thức.",
            "Kiểm tra điều kiện miền xác định, hội tụ hoặc tham số không làm mẫu số bằng 0.",
            "Áp dụng đúng định nghĩa, phương trình vi phân hoặc biểu diễn tích phân của hàm.",
            "Thay tham số vào đúng vị trí và giữ nguyên biến/chỉ số bị ràng buộc.",
            "Viết công thức cuối cùng bằng LaTeX chuẩn.",
        ],
        "logarithm": [
            "Xác định cơ số, đối số và giá trị logarit trong biểu thức.",
            "Kiểm tra điều kiện cơ số dương khác 1 và đối số dương.",
            "Áp dụng đúng định nghĩa hoặc quy tắc logarit: tích, thương, lũy thừa hoặc đổi cơ số.",
            "Thay dữ kiện vào đúng vị trí cơ số và đối số, không đảo tử mẫu khi dùng đổi cơ số.",
            "Rút gọn và viết kết quả bằng LaTeX chuẩn.",
        ],
        "radical": [
            "Xác định bậc căn, biểu thức dưới dấu căn và các tham số liên quan.",
            "Kiểm tra điều kiện miền xác định của căn, đặc biệt căn bậc chẵn cần biểu thức không âm.",
            "Áp dụng đúng quy tắc căn thức hoặc lũy thừa phân số.",
            "Thay dữ kiện vào đúng vị trí trong căn và rút gọn thừa số nếu có.",
            "Viết kết quả cuối cùng bằng LaTeX chuẩn.",
        ],
        "exponent": [
            "Xác định cơ số và các số mũ trong biểu thức.",
            "Kiểm tra điều kiện của cơ số nếu có số mũ phân số, logarit hoặc căn thức.",
            "Áp dụng đúng quy tắc lũy thừa: nhân cùng cơ số, lũy thừa của lũy thừa hoặc lũy thừa của tích.",
            "Thay số vào đúng cơ số/số mũ và thực hiện phép tính theo thứ tự.",
            "Rút gọn và viết kết quả bằng LaTeX chuẩn.",
        ],
    }

    return template_map.get(
        topic,
        [
            f"Xác định dữ kiện và công thức cần dùng cho yêu cầu: {instruction}.",
            f"Đối chiếu với dạng chuẩn của công thức: \\({formula}\\).",
            f"Kiểm tra điều kiện áp dụng: {constraint_text}.",
            "Thay các giá trị đã biết vào đúng ký hiệu, tránh đổi vai trò của biến hoặc chỉ số.",
            "Rút gọn và viết kết quả cuối cùng bằng LaTeX chuẩn.",
        ],
    )


def fmt_num(value):
    if isinstance(value, Fraction):
        return fmt_frac(value)
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def fmt_frac(value):
    frac = value if isinstance(value, Fraction) else Fraction(value)
    if frac.denominator == 1:
        return str(frac.numerator)
    sign = "-" if frac.numerator < 0 else ""
    return f"{sign}\\frac{{{abs(frac.numerator)}}}{{{frac.denominator}}}"


def frac_example(input_values, result):
    return {"input_values": input_values, "output": fmt_frac(result)}


def fraction_examples(item):
    text = norm_text(item)
    if "subtract_same" in item.get("id", "") or ("trừ" in text and "cùng mẫu" in text):
        return [
            frac_example({"numerator_1": 5, "numerator_2": 2, "denominator": 7}, Fraction(3, 7)),
            frac_example({"numerator_1": -5, "numerator_2": 7, "denominator": 8}, Fraction(-12, 8)),
        ]
    if "multiply" in item.get("id", "") or "nhân hai phân" in text:
        return [
            frac_example({"numerator_1": 2, "denominator_1": 3, "numerator_2": 3, "denominator_2": 5}, Fraction(6, 15)),
            frac_example({"numerator_1": -4, "denominator_1": 7, "numerator_2": 14, "denominator_2": 3}, Fraction(-56, 21)),
        ]
    if "divide" in item.get("id", "") or "chia hai phân" in text:
        return [
            frac_example({"numerator_1": 2, "denominator_1": 3, "numerator_2": 4, "denominator_2": 5}, Fraction(10, 12)),
            frac_example({"numerator_1": -3, "denominator_1": 8, "numerator_2": 9, "denominator_2": 4}, Fraction(-12, 72)),
        ]
    if "add_different" in item.get("id", "") or ("cộng" in text and "khác mẫu" in text):
        return [
            frac_example({"numerator_1": 1, "denominator_1": 2, "numerator_2": 1, "denominator_2": 3}, Fraction(5, 6)),
            frac_example({"numerator_1": 3, "denominator_1": 4, "numerator_2": -2, "denominator_2": 5}, Fraction(7, 20)),
        ]
    if "subtract_different" in item.get("id", "") or ("trừ" in text and "khác mẫu" in text):
        return [
            frac_example({"numerator_1": 3, "denominator_1": 4, "numerator_2": 1, "denominator_2": 6}, Fraction(7, 12)),
            frac_example({"numerator_1": 2, "denominator_1": 5, "numerator_2": 3, "denominator_2": 10}, Fraction(1, 10)),
        ]
    return generic_examples(item)


def probability_examples(item):
    formula = item_formula(item)
    f = formula.replace(" ", "")
    text = norm_text(item)

    if "bayes" in text and "\\sum" not in f:
        return [
            {
                "input_values": {"P_A": 0.30, "P_B_given_A": 0.80, "P_B": 0.40},
                "output": "P(A \\mid B)=\\frac{0.80\\cdot0.30}{0.40}=0.60",
            },
            {
                "input_values": {"P_A": 0.20, "P_B_given_A": 0.75, "P_B": 0.50},
                "output": "P(A \\mid B)=\\frac{0.75\\cdot0.20}{0.50}=0.30",
            },
        ]
    if "bayes" in text and "\\sum" in f:
        return [
            {
                "input_values": {"P_A": 0.30, "P_B_given_A": 0.80, "P_B": 0.48},
                "output": "P(A \\mid B)=\\frac{0.80\\cdot0.30}{0.48}=0.50",
            }
        ]
    if ("P(A\\capB)" in f or "P(A\\capB)" in f.replace("\\mid", "|")) and ("/P(B)" in f or "{P(B)}" in f) and "P(B|A)" not in f:
        return [
            {
                "input_values": {"P_A_inter_B": 0.18, "P_B": 0.30},
                "output": "P(A \\mid B)=\\frac{0.18}{0.30}=0.60",
            },
            {
                "input_values": {"P_A_inter_B": 0.12, "P_B": 0.48},
                "output": "P(A \\mid B)=\\frac{0.12}{0.48}=0.25",
            },
        ]
    if "\\cup" in f:
        return [
            {
                "input_values": {"P_A": 0.35, "P_B": 0.50, "P_A_inter_B": 0.20},
                "output": "P(A \\cup B)=0.35+0.50-0.20=0.65",
            },
            {
                "input_values": {"P_A": 0.40, "P_B": 0.25, "P_A_inter_B": 0.10},
                "output": "P(A \\cup B)=0.40+0.25-0.10=0.55",
            },
        ]
    if "\\cap" in f and ("P(A|B)" in f or "P(B\\midA)" in f or "P(B\\mid A)" in formula):
        return [
            {
                "input_values": {"P_A_given_B": 0.60, "P_B": 0.30},
                "output": "P(A \\cap B)=0.60\\cdot0.30=0.18",
            },
            {
                "input_values": {"P_A": 0.40, "P_B_given_A": 0.25},
                "output": "P(A \\cap B)=0.40\\cdot0.25=0.10",
            },
        ]
    if "\\cap" in f and "P(A)P(B)" in f:
        return [
            {
                "input_values": {"P_A": 0.40, "P_B": 0.25},
                "output": "P(A \\cap B)=0.40\\cdot0.25=0.10",
            }
        ]
    if "favorable" in f or "cổ điển" in text:
        return [
            {
                "input_values": {"favorable_outcomes": 3, "total_outcomes": 12},
                "output": "P(A)=\\frac{3}{12}=\\frac{1}{4}",
            },
            {
                "input_values": {"favorable_outcomes": 5, "total_outcomes": 20},
                "output": "P(A)=\\frac{5}{20}=\\frac{1}{4}",
            },
        ]
    if "\\binom{n}{k}" in f and "p^k" in f:
        return [
            {
                "input_values": {"n": 5, "k": 2, "p": 0.40},
                "output": "P(X=2)=\\binom{5}{2}(0.40)^2(0.60)^3=0.3456",
            },
            {
                "input_values": {"n": 4, "k": 1, "p": 0.25},
                "output": "P(X=1)=\\binom{4}{1}(0.25)(0.75)^3=0.421875",
            },
        ]
    if "\\lambda^k" in f and "k!" in f:
        return [
            {
                "input_values": {"lambda": 3, "k": 2},
                "output": "P(X=2)=\\frac{3^2e^{-3}}{2!}\\approx0.224",
            }
        ]
    if "lambda e" in f or "\\lambda e" in f:
        return [
            {
                "input_values": {"lambda": 0.5, "x": 2},
                "output": "f(2)=0.5e^{-0.5\\cdot2}\\approx0.184",
            }
        ]
    if "gaussian" in text or "chuẩn" in text or "normal" in text:
        return [
            {
                "input_values": {"x": 1, "mu": 0, "sigma": 2},
                "output": "f(1)=\\frac{1}{2\\sqrt{2\\pi}}e^{-\\frac{(1-0)^2}{2\\cdot2^2}}",
            }
        ]
    if "kỳ vọng" in text or "ky vong" in text or "\\mathbb{e}" in text or "e(x)" in text:
        return [
            {
                "input_values": {"values": [1, 2, 3], "probabilities": [0.2, 0.5, 0.3]},
                "output": "\\mathbb{E}[X]=1\\cdot0.2+2\\cdot0.5+3\\cdot0.3=2.1",
            }
        ]
    if "var" in text or "phương sai" in text:
        return [
            {
                "input_values": {"E_X2": 5.0, "E_X": 2.0},
                "output": "\\operatorname{Var}(X)=5.0-2.0^2=1.0",
            }
        ]
    if "cov" in text or "hiệp phương sai" in text or "tương quan" in text:
        return [
            {
                "input_values": {"Cov_XY": 6, "sigma_X": 2, "sigma_Y": 3},
                "output": "\\rho(X,Y)=\\frac{6}{2\\cdot3}=1",
            }
        ]
    if "entropy" in text:
        return [
            {
                "input_values": {"probabilities": [0.5, 0.5]},
                "output": "H(X)=-(0.5\\log 0.5+0.5\\log 0.5)",
            }
        ]
    if "logistic" in text:
        return [
            {
                "input_values": {"theta_T_x": 1.2},
                "output": "P(y=1\\mid x)=\\sigma(1.2)=\\frac{1}{1+e^{-1.2}}",
            }
        ]
    if "likelihood" in text or "mle" in text:
        return [
            {
                "input_values": {"sample_size": 3},
                "output": "\\hat{\\theta}_{MLE}=\\arg\\max_{\\theta}\\prod_{i=1}^{3}p(x_i\\mid\\theta)",
            }
        ]
    if "map" in text or "posterior" in text:
        return [
            {
                "input_values": {"posterior": "p(\\theta\\mid X)"},
                "output": "\\hat{\\theta}_{MAP}=\\arg\\max_{\\theta}p(\\theta\\mid X)",
            }
        ]
    if "collision" in text or "birthday" in text:
        return [
            {
                "input_values": {"k": 1000, "N": 1000000},
                "output": "P(\\text{collision})\\approx1-e^{-1000^2/(2\\cdot1000000)}",
            }
        ]
    return task_example(item)


def combinatorics_examples(item):
    return [
        {
            "input_values": {"total_elements": 5, "selected_elements": 2},
            "output": "\\binom{5}{2}=10",
        },
        {
            "input_values": {"total_elements": 6, "selected_elements": 3},
            "output": "\\binom{6}{3}=20",
        },
    ]


def crypto_examples(item):
    formula = item_formula(item).replace(" ", "")
    text = norm_text(item)
    if formula == "n=p\\cdotq":
        return [{"input_values": {"p": 11, "q": 17}, "output": "n=11\\cdot17=187"}]
    if "\\phi(n)" in formula and "(p-1)" in formula:
        return [{"input_values": {"p": 11, "q": 17}, "output": "\\phi(n)=(11-1)(17-1)=160"}]
    if "ed\\equiv1" in formula:
        return [{"input_values": {"e": 7, "d": 23, "phi_n": 160}, "output": "7\\cdot23\\equiv1\\pmod{160}"}]
    if formula.startswith("c=m^e"):
        return [{"input_values": {"m": 7, "e": 5, "n": 33}, "output": "c=7^5\\bmod 33=10"}]
    if formula.startswith("m=c^d"):
        return [{"input_values": {"c": 10, "d": 13, "n": 33}, "output": "m=10^{13}\\bmod 33=7"}]
    if "g^x\\modp" in formula or "g^x\\bmodp" in formula:
        return [{"input_values": {"g": 5, "x": 3, "p": 13}, "output": "5^3\\bmod 13=8"}]
    if "g^{ab}" in formula:
        return [{"input_values": {"g": 5, "a": 3, "b": 4, "p": 23}, "output": "K=5^{12}\\bmod 23=18"}]
    if "h(k)=k\\modm" in formula:
        return [{"input_values": {"k": 37, "m": 10}, "output": "h(37)=37\\bmod 10=7"}]
    if "alpha=n/m" in formula or "\\alpha=\\frac{n}{m}" in formula:
        return [{"input_values": {"n": 30, "m": 100}, "output": "\\alpha=\\frac{30}{100}=0.3"}]
    if "mod" in text or "pmod" in text:
        return [{"input_values": {"a": 17, "n": 5}, "output": "17\\equiv2\\pmod{5}"}]
    return generic_examples(item)


def latex_value(value):
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def replace_symbol(expr, symbol, value):
    if not symbol:
        return expr
    value_text = latex_value(value)
    if symbol.startswith("\\"):
        pattern = re.compile(re.escape(symbol) + r"(?![A-Za-z])")
        return pattern.sub(lambda _: value_text, expr)
    if re.fullmatch(r"[A-Za-z]", symbol):
        pattern = re.compile(rf"(?<![A-Za-z0-9\\]){re.escape(symbol)}(?![A-Za-z0-9_])")
        return pattern.sub(lambda _: value_text, expr)
    pattern = re.compile(re.escape(symbol))
    return pattern.sub(lambda _: value_text, expr)


SKIP_ROLES = {
    "formula",
    "result",
    "area",
    "volume",
    "perimeter",
    "total_surface_area",
    "function",
    "dependent_variable",
    "mapping",
    "combinations",
    "set",
    "universe",
    "element",
    "vector",
    "matrix",
    "vector_b",
    "constants",
    "functions",
    "first_function",
    "second_function",
    "integration_variable",
    "independent_variable",
    "gamma_function",
    "bessel_function",
}


def unsafe_symbol(symbol):
    if not isinstance(symbol, str) or not symbol:
        return True
    if symbol in {"i", "j", "k"}:
        return True
    if "_" in symbol and not symbol.startswith("\\"):
        return True
    if any(part in symbol for part in ["\\mathbf", "\\mathbb", "\\operatorname", "{", "}", ",", "..."]):
        return True
    if len(symbol) > 12 and not symbol.startswith("\\"):
        return True
    return False


def is_bound_symbol(formula, symbol):
    if not re.fullmatch(r"[A-Za-z]", symbol):
        return False
    escaped = re.escape(symbol)
    patterns = [
        rf"\\sum_\{{?{escaped}=",
        rf"\\prod_\{{?{escaped}=",
        rf"\\int.*d{escaped}(?![A-Za-z])",
        rf"\\frac\{{d\}}\{{d{escaped}\}}",
        rf"\\frac\{{\\partial\}}\{{\\partial {escaped}\}}",
    ]
    return any(re.search(pattern, formula) for pattern in patterns)


def has_implicit_adjacent_symbol(formula, symbol):
    if not re.fullmatch(r"[A-Za-z]", symbol):
        return False
    escaped = re.escape(symbol)
    return bool(
        re.search(rf"(?<!\\)(?<=[A-Za-z0-9]){escaped}", formula)
        or re.search(rf"(?<!\\){escaped}(?=[A-Za-z0-9])", formula)
    )


def sample_value(role, symbol, index, topic):
    angle_values = ["30^\\circ", "45^\\circ"]
    if "angle" in role or symbol in {"\\theta", "\\alpha", "\\beta"}:
        return angle_values[index % 2]
    if symbol in {"\\mu", "mu"} or "mean" in role:
        return [10, 12][index % 2]
    if symbol in {"\\sigma", "sigma"}:
        return [2, 3][index % 2]
    if symbol in {"\\lambda", "lambda"}:
        return [0.5, 2][index % 2]
    if role in {"sample_size", "number_of_terms", "order"} or symbol in {"n", "N"}:
        return [5, 8][index % 2]
    if "selected" in role or symbol in {"r", "k"}:
        return [2, 3][index % 2]
    if symbol in {"p"} and topic == "probability":
        return [0.4, 0.25][index % 2]
    defaults = {
        "x": [2, 3],
        "y": [4, 5],
        "z": [6, 7],
        "w": [1, 2],
        "u": [1, 2],
        "v": [3, 4],
        "a": [2, 3],
        "b": [3, 4],
        "c": [4, 5],
        "d": [5, 6],
        "m": [7, 9],
        "q": [11, 13],
        "R": [5, 6],
    }
    return defaults.get(symbol, [2, 3])[index % 2]


def bad_example_output(output):
    return bool(
        re.search(r"\b\d+_i\b", output)
        or re.search(r"\bd\d+\b", output)
        or re.search(r"\b\d+\^\{\(i\)\}", output)
        or re.search(r"softma\d", output)
        or re.search(r"(?<!\\)\b(cap|cup|mid|equiv|pmod)\b", output)
    )


def task_example(item):
    return [
        {
            "input_values": {
                "task": as_text(item.get("instruction")),
                "input": as_text(item.get("input")),
            },
            "output": item_formula(item),
        }
    ]


def generic_examples(item, topic=None):
    topic = topic or classify(item)
    formula = item_formula(item)
    variables = item.get("variables") if isinstance(item.get("variables"), dict) else {}
    examples = []

    for index in range(2):
        substitutions = {}
        input_values = {}
        for role, symbol in variables.items():
            role_text = str(role)
            symbol_text = str(symbol)
            if role_text in SKIP_ROLES or unsafe_symbol(symbol_text):
                continue
            if is_bound_symbol(formula, symbol_text):
                continue
            if has_implicit_adjacent_symbol(formula, symbol_text):
                continue
            if "\\int" in formula and symbol_text == "x":
                continue
            if "\\frac{d" in formula and symbol_text == "x":
                continue
            value = sample_value(role_text, symbol_text, index, topic)
            substitutions[symbol_text] = value
            input_values[role_text] = value

        output = formula
        for symbol, value in sorted(substitutions.items(), key=lambda pair: len(pair[0]), reverse=True):
            output = replace_symbol(output, symbol, value)

        if not substitutions or output == formula or bad_example_output(output):
            continue
        examples.append({"input_values": input_values, "output": output})

    return examples or task_example(item)


def build_examples(item, topic):
    if topic == "fraction":
        return fraction_examples(item)
    if topic == "probability":
        return probability_examples(item)
    if topic == "combinatorics":
        return combinatorics_examples(item)
    if topic == "number_theory_crypto":
        return crypto_examples(item)
    return generic_examples(item, topic)


def retag_item(item, topic):
    tags = list(item.get("tags") or [])
    type_by_topic = {
        "probability": "statistics",
        "integral": "calculus",
        "derivative": "calculus",
        "limit": "calculus",
        "logarithm": "algebra",
        "radical": "algebra",
        "exponent": "algebra",
        "fraction": "algebra",
        "number_theory_crypto": "algebra",
        "machine_learning": "machine_learning",
    }
    if topic == "probability":
        if "probability" not in tags:
            tags.append("probability")
        if item.get("type") == "algebra" and not has_any(norm_text(item), ["logistic", "mle", "map", "naive bayes", "gmm"]):
            item["type"] = "statistics"
    if topic == "number_theory_crypto":
        tags = [tag for tag in tags if tag != "probability"]
        for tag in ["number_theory", "cryptography"]:
            if tag not in tags:
                tags.append(tag)
    if topic not in {"probability", "combinatorics"} and not has_probability_evidence(item):
        tags = [tag for tag in tags if tag != "probability"]
    if topic in type_by_topic:
        item["type"] = type_by_topic[topic]
    item["tags"] = tags


def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8-sig"))
    stats = {"records": len(data), "steps_updated": 0, "examples_updated": 0, "retagged": 0}

    for item in data:
        old_tags = list(item.get("tags") or [])
        old_type = item.get("type")
        topic = classify(item)
        new_steps = build_steps(item, topic)
        new_examples = build_examples(item, topic)

        if item.get("steps") != new_steps:
            item["steps"] = new_steps
            stats["steps_updated"] += 1
        if item.get("example_problems") != new_examples:
            item["example_problems"] = new_examples
            stats["examples_updated"] += 1

        retag_item(item, topic)
        if old_tags != item.get("tags") or old_type != item.get("type"):
            stats["retagged"] += 1

    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
