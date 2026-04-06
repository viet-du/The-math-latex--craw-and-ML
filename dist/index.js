"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const cheerio_1 = require("cheerio");
const mathml_to_latex_1 = require("mathml-to-latex");
const puppeteer_1 = __importDefault(require("puppeteer"));
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36';
const normalizeWhitespace = (value) => value.replace(/\s+/g, ' ').trim();
const normalizePathname = (value) => {
    const normalized = value.replace(/\/+/g, '/');
    if (!normalized || normalized === '/')
        return '/';
    return normalized.endsWith('/') ? normalized : `${normalized}/`;
};
const decodeHtml = (value) => (0, cheerio_1.load)(`<div>${value}</div>`)('div').text();
const replaceLatexLikeSymbols = (value) => value
    .replace(/⋅/g, '\\cdot ')
    .replace(/×/g, '\\times ')
    .replace(/÷/g, '\\div ') // THÊM: phép chia
    .replace(/≤/g, '\\le ') // SỬA: dùng \le thay vì \leq
    .replace(/≥/g, '\\ge ') // SỬA: dùng \ge thay vì \geq
    .replace(/≠/g, '\\ne ')
    .replace(/≈/g, '\\approx ') // THÊM: xấp xỉ
    .replace(/∞/g, '\\infty ')
    .replace(/∑/g, '\\sum ')
    .replace(/∏/g, '\\prod ')
    .replace(/∫/g, '\\int ')
    .replace(/∮/g, '\\oint ') // THÊM: tích phân đường
    .replace(/√/g, '\\sqrt{}')
    .replace(/±/g, '\\pm ')
    .replace(/∓/g, '\\mp ') // THÊM: dấu trừ cộng
    .replace(/∂/g, '\\partial ') // THÊM: đạo hàm riêng
    .replace(/∇/g, '\\nabla ') // THÊM: gradient
    .replace(/∈/g, '\\in ') // THÊM: thuộc
    .replace(/∉/g, '\\notin ') // THÊM: không thuộc
    .replace(/⊂/g, '\\subset ') // THÊM: tập con
    .replace(/⊆/g, '\\subseteq ') // THÊM: tập con hoặc bằng
    .replace(/⊃/g, '\\supset ') // THÊM: tập chứa
    .replace(/∩/g, '\\cap ') // THÊM: giao
    .replace(/∪/g, '\\cup ') // THÊM: hợp
    .replace(/∀/g, '\\forall ') // THÊM: với mọi
    .replace(/∃/g, '\\exists ') // THÊM: tồn tại
    .replace(/∄/g, '\\nexists ') // THÊM: không tồn tại
    .replace(/→/g, '\\to ') // THÊM: mũi tên
    .replace(/⇒/g, '\\Rightarrow ')
    .replace(/⇔/g, '\\Leftrightarrow ')
    .replace(/π/g, '\\pi ')
    .replace(/τ/g, '\\tau ') // THÊM: tau
    .replace(/θ/g, '\\theta ') // THÊM: theta
    .replace(/φ/g, '\\phi ')
    .replace(/ψ/g, '\\psi ') // THÊM: psi
    .replace(/ω/g, '\\omega ')
    .replace(/α/g, '\\alpha ')
    .replace(/β/g, '\\beta ')
    .replace(/γ/g, '\\gamma ')
    .replace(/δ/g, '\\delta ') // THÊM: delta
    .replace(/ε/g, '\\epsilon ') // THÊM: epsilon
    .replace(/λ/g, '\\lambda ')
    .replace(/μ/g, '\\mu ')
    .replace(/σ/g, '\\sigma ')
    .replace(/Σ/g, '\\Sigma ') // THÊM: Sigma hoa
    .replace(/Δ/g, '\\Delta ')
    .replace(/Ω/g, '\\Omega ') // THÊM: Omega hoa
    .replace(/Γ/g, '\\Gamma ') // THÊM: Gamma hoa
    .replace(/Θ/g, '\\Theta ') // THÊM: Theta hoa
    .replace(/Λ/g, '\\Lambda ') // THÊM: Lambda hoa
    .replace(/Φ/g, '\\Phi ') // THÊM: Phi hoa
    .replace(/Ψ/g, '\\Psi '); // THÊM: Psi hoa
const stripMathDelimiters = (value) => value.replace(/^\\\[\s*|\s*\\\]$/g, '');
const extractMathsIsFunFormulas = ($, pageTitle, pageUrl) => {
    const records = [];
    const subjectSlug = getSubjectSlug(pageUrl);
    const subjectPath = getSubjectPath(pageUrl);
    let currentSection = '';
    let currentSubsection = '';
    // Xử lý các thẻ <span class="large"> chứa công thức
    $('span.large').each((_, element) => {
        // Clone element để không ảnh hưởng đến DOM gốc
        const $clone = $(element).clone();
        // Xử lý các thẻ con đặc biệt
        $clone.find('sup').each((_, sup) => {
            const supText = $(sup).text();
            $(sup).replaceWith(`^{${supText}}`);
        });
        $clone.find('sub').each((_, sub) => {
            const subText = $(sub).text();
            $(sub).replaceWith(`_{${subText}}`);
        });
        $clone.find('span.eq').each((_, eq) => {
            const eqText = $(eq).text();
            if (eqText === '=') {
                $(eq).replaceWith('=');
            }
            else {
                $(eq).replaceWith(eqText);
            }
        });
        // Lấy text đã được xử lý
        const rawText = $clone.text();
        // Phát hiện công thức có dấu =
        if (rawText.includes('=') && rawText.length > 1 && rawText.length < 200) {
            // Lấy section context từ heading gần nhất
            const $heading = $(element).closest('div, section').prevAll('h2, h3').first();
            if ($heading.length > 0) {
                const headingTag = $heading.prop('tagName')?.toLowerCase();
                if (headingTag === 'h2') {
                    currentSection = cleanHeadingText($heading.text());
                    currentSubsection = '';
                }
                else if (headingTag === 'h3') {
                    currentSubsection = cleanHeadingText($heading.text());
                }
            }
            // Chuẩn hóa và thêm vào records
            const normalized = normalizeFormulaInput(rawText);
            if (normalized?.latex) {
                records.push({
                    latex: normalized.latex,
                    pageTitle,
                    pageUrl,
                    subjectSlug,
                    subjectPath,
                    section: currentSection || 'Laws of Exponents',
                    subsection: currentSubsection,
                    formulaName: '',
                    source: 'mathsisfun-large-span',
                    indexInPage: records.length + 1,
                });
            }
        }
    });
    // Xử lý các bảng công thức (Law | Example)
    $('table').each((_, table) => {
        const $rows = $(table).find('tr');
        let isFormulaTable = false;
        // Kiểm tra xem bảng có chứa công thức không
        $rows.each((_, row) => {
            const rowText = $(row).text();
            if (rowText.includes('x1') || rowText.includes('xm') || rowText.includes('xn')) {
                isFormulaTable = true;
            }
        });
        if (isFormulaTable) {
            $rows.each((_, row) => {
                const $cells = $(row).find('td');
                if ($cells.length >= 2) {
                    const lawText = $cells.eq(0).text().trim();
                    const exampleText = $cells.eq(1).text().trim();
                    if (lawText && exampleText && (lawText.includes('=') || exampleText.includes('='))) {
                        // Lấy section từ heading trước bảng
                        const $heading = $(table).prevAll('h2, h3').first();
                        if ($heading.length > 0) {
                            const headingTag = $heading.prop('tagName')?.toLowerCase();
                            if (headingTag === 'h2') {
                                currentSection = cleanHeadingText($heading.text());
                                currentSubsection = '';
                            }
                            else if (headingTag === 'h3') {
                                currentSubsection = cleanHeadingText($heading.text());
                            }
                        }
                        // Xử lý law text
                        let lawLatex = lawText
                            .replace(/x1/g, 'x^{1}')
                            .replace(/x0/g, 'x^{0}')
                            .replace(/x-1/g, 'x^{-1}')
                            .replace(/xmxn/g, 'x^{m}x^{n}')
                            .replace(/xm\/xn/g, '\\frac{x^{m}}{x^{n}}')
                            .replace(/\(xm\)n/g, '(x^{m})^{n}')
                            .replace(/\(xy\)n/g, '(xy)^{n}')
                            .replace(/\(x\/y\)n/g, '(\\frac{x}{y})^{n}')
                            .replace(/x-n/g, 'x^{-n}')
                            .replace(/xm\/n/g, 'x^{m/n}');
                        const normalized = normalizeFormulaInput(lawLatex);
                        if (normalized?.latex) {
                            records.push({
                                latex: normalized.latex,
                                pageTitle,
                                pageUrl,
                                subjectSlug,
                                subjectPath,
                                section: currentSection || 'Laws of Exponents',
                                subsection: currentSubsection,
                                formulaName: lawText.substring(0, 50),
                                source: 'mathsisfun-table-law',
                                indexInPage: records.length + 1,
                            });
                        }
                        // Xử lý example text
                        let exampleLatex = exampleText
                            .replace(/61\s*=\s*6/g, '6^{1}=6')
                            .replace(/70\s*=\s*1/g, '7^{0}=1')
                            .replace(/4-1\s*=\s*1\/4/g, '4^{-1}=\\frac{1}{4}')
                            .replace(/x2x3\s*=\s*x2\+3\s*=\s*x5/g, 'x^{2}x^{3}=x^{2+3}=x^{5}');
                        const normalizedExample = normalizeFormulaInput(exampleLatex);
                        if (normalizedExample?.latex) {
                            records.push({
                                latex: normalizedExample.latex,
                                pageTitle,
                                pageUrl,
                                subjectSlug,
                                subjectPath,
                                section: currentSection || 'Laws of Exponents',
                                subsection: currentSubsection,
                                formulaName: `Example: ${lawText}`,
                                source: 'mathsisfun-table-example',
                                indexInPage: records.length + 1,
                            });
                        }
                    }
                }
            });
        }
    });
    return records;
};
const isMathmlMarkup = (value) => /<(math|mrow|mi|mn|mo|msup|msub|mfrac|msqrt|mroot|mtable|mtr|mtd|mfenced|mover|munder|munderover|msubsup|mmultiscripts|mstyle|merror)\b/i.test(value);
const detectFormulaType = (input) => {
    if (input.includes('\\') || input.includes('$'))
        return 'latex';
    if (isMathmlMarkup(input))
        return 'mathml';
    return 'text';
};
const normalizeImplicitPowers = (value) => {
    const superscriptMap = {
        '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
        '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
        '⁺': '+', '⁻': '-', '⁼': '=', '⁽': '(', '⁾': ')'
    };
    const subscriptMap = {
        '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
        '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
        '₊': '+', '₋': '-', '₌': '=', '₍': '(', '₎': ')'
    };
    const functionNames = new Set(['sin', 'cos', 'tan', 'sec', 'csc', 'cot',
        'log', 'ln', 'exp', 'sinh', 'cosh', 'tanh']);
    // Xử lý unicode superscript
    let result = value.replace(/([A-Za-z0-9\)])([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾]+)/g, (_, base, sup) => {
        const converted = sup.split('').map((ch) => superscriptMap[ch] || ch).join(''); // THÊM kiểu :string
        return `${base}^{${converted}}`;
    });
    // Xử lý unicode subscript
    result = result.replace(/([A-Za-z0-9\)])([₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎]+)/g, (_, base, sub) => {
        const converted = sub.split('').map((ch) => subscriptMap[ch] || ch).join(''); // THÊM kiểu :string
        return `${base}_{${converted}}`;
    });
    // Xử lý implicit powers (x2 -> x^2)
    result = result.replace(/([A-Za-z])([2-9])(?!\d)/g, (match, letter, digit, offset, source) => {
        const prefix = source.slice(0, offset + 1);
        const currentWord = prefix.match(/[A-Za-z]+$/)?.[0]?.toLowerCase() ?? '';
        if (currentWord.length > 1 && functionNames.has(currentWord)) {
            return match; // Giữ nguyên sin2, cos2, v.v.
        }
        return `${letter}^{${digit}}`;
    });
    return result;
};
const textToLatex = (text) => {
    let result = text;
    // Xử lý căn bậc hai và căn bậc n
    result = result.replace(/sqrt\((.*?)\)/g, '\\sqrt{$1}');
    result = result.replace(/sqrt\[(\d+)\]\((.*?)\)/g, '\\sqrt[$1]{$2}');
    // Xử lý phân số với tử số và mẫu số phức tạp
    result = result.replace(/([a-zA-Z0-9\(\)]+)\s*\/\s*([a-zA-Z0-9\(\)]+)/g, '\\frac{$1}{$2}');
    // Xử lý lũy thừa
    result = result.replace(/\^(\d+)/g, '^{$1}');
    result = result.replace(/\^\{([^}]+)\}/g, '^{$1}');
    result = result.replace(/([a-zA-Z])([⁰¹²³⁴⁵⁶⁷⁸⁹]+)/g, (_, base, sup) => {
        const supMap = { '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9' };
        const converted = sup.split('').map((ch) => supMap[ch] || ch).join(''); // THÊM kiểu :string
        return `${base}^{${converted}}`;
    });
    // Xử lý ký tự đặc biệt
    result = result
        .replace(/\*/g, '\\cdot ')
        .replace(/\.\.\./g, '\\ldots ')
        .replace(/->/g, '\\to ')
        .replace(/=>/g, '\\Rightarrow ')
        .replace(/<=/g, '\\Leftarrow ')
        .replace(/<>/g, '\\neq ');
    return normalizeImplicitPowers(result);
};
const normalizeVectorNotation = (value) => value.replace(/([A-Za-z\u00C0-\u024F\u0370-\u03FF])\u20D7/g, '\\\\vec{$1}');
const normalizeLatex = (value) => {
    const decoded = decodeHtml(value)
        .replace(/\r/g, '')
        .replace(/\$+/g, '')
        .replace(/\\displaystyle/g, '')
        .replace(/\\textstyle/g, '')
        .replace(/\\scriptstyle/g, '')
        .replace(/&nbsp;/g, ' ')
        .replace(/\u00A0/g, ' ')
        .replace(/[–—−]/g, '-');
    let withSymbols = replaceLatexLikeSymbols(stripMathDelimiters(normalizeVectorNotation(decoded)));
    // Xử lý các dạng đặc biệt
    withSymbols = withSymbols
        // Binomial
        .replace(/\\binom\s*\{([^}]+)\}\s*\{([^}]+)\}/g, '\\binom{$1}{$2}')
        // Matrix
        .replace(/\\begin\{matrix\}/g, '\\begin{matrix}')
        .replace(/\\end\{matrix\}/g, '\\end{matrix}')
        // Cases
        .replace(/\\begin\{cases\}/g, '\\begin{cases}')
        .replace(/\\end\{cases\}/g, '\\end{cases}')
        // Brackets
        .replace(/\\left\(/g, '\\left(')
        .replace(/\\right\)/g, '\\right)')
        .replace(/\\left\[/g, '\\left[')
        .replace(/\\right\]/g, '\\right]')
        .replace(/\\left\{/g, '\\left\\{')
        .replace(/\\right\}/g, '\\right\\}')
        // Operators
        .replace(/\\lim\s*([a-z]+)/g, '\\lim $1')
        .replace(/\\log\s*_(\d+)/g, '\\log_{$1}')
        .replace(/\\ln\s*([a-z]+)/g, '\\ln $1');
    return withSymbols
        .replace(/\\\s+(?=[^a-zA-Z])/g, '\\\\ ')
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
        .join(' ')
        .replace(/\s+/g, ' ')
        .trim();
};
const normalizeFormulaInput = (input) => {
    const type = detectFormulaType(input);
    try {
        let latex = null;
        if (type === 'latex') {
            latex = normalizeLatex(input);
        }
        else if (type === 'mathml') {
            latex = normalizeLatex(mathml_to_latex_1.MathMLToLaTeX.convert(input));
        }
        else {
            latex = normalizeLatex(textToLatex(input));
        }
        if (!latex)
            return null;
        // Lọc bỏ các công thức có nội dung giống ví dụ
        if (!isFormulaContent(latex)) {
            return null;
        }
        return { latex, type };
    }
    catch {
        return null;
    }
};
const toAbsoluteUrl = (link, currentUrl) => {
    try {
        const absoluteUrl = new URL(link, currentUrl);
        absoluteUrl.hash = '';
        return absoluteUrl.toString();
    }
    catch {
        return null;
    }
};
const getPathSegments = (pageUrl) => new URL(pageUrl).pathname.split('/').filter(Boolean);
const deriveScopePathPrefix = (pageUrl) => {
    const segments = getPathSegments(pageUrl);
    if (segments[0] === 'subjects' && segments.length >= 2) {
        return normalizePathname(`/${segments.slice(0, 2).join('/')}`);
    }
    if (segments.length <= 1) {
        return normalizePathname(new URL(pageUrl).pathname);
    }
    return normalizePathname(`/${segments.slice(0, -1).join('/')}`);
};
const getSubjectSlug = (pageUrl) => {
    const segments = getPathSegments(pageUrl);
    if (segments[0] === 'subjects' && segments.length >= 2) {
        return segments[1];
    }
    return segments[0] ?? 'general';
};
const getSubjectPath = (pageUrl) => deriveScopePathPrefix(pageUrl);
const isAllowedPage = (rawUrl, startHost, scopePathPrefix, ignoredPathFragments) => {
    try {
        const url = new URL(rawUrl);
        // THÊM: Chỉ cho phép crawl các trang từ vietjack.com
        const allowedHosts = ['www.vietjack.com', 'vietjack.com'];
        if (!allowedHosts.includes(url.host)) {
            return false;
        }
        if (!['http:', 'https:'].includes(url.protocol))
            return false;
        if (ignoredPathFragments.some((fragment) => rawUrl.includes(fragment) || url.pathname.includes(fragment))) {
            return false;
        }
        if (!url.pathname || url.pathname === '/')
            return false;
        if (/\.(png|jpg|jpeg|gif|webp|svg|pdf|xml)$/i.test(url.pathname))
            return false;
        if (!normalizePathname(url.pathname).startsWith(scopePathPrefix))
            return false;
        return true;
    }
    catch {
        return false;
    }
};
const collectUniqueValues = (values) => {
    const seen = new Set();
    const results = [];
    for (const value of values) {
        if (!value)
            continue;
        const latex = normalizeLatex(value);
        if (!latex)
            continue;
        if (seen.has(latex))
            continue;
        seen.add(latex);
        results.push(latex);
    }
    return results;
};
const htmlToTextWithBreaks = (html) => {
    const withLineBreaks = html.replace(/<br\s*\/?>/gi, '\n');
    const withScripts = withLineBreaks
        .replace(/<sup[^>]*>([\s\S]*?)<\/sup>/gi, '^{$1}')
        .replace(/<sub[^>]*>([\s\S]*?)<\/sub>/gi, '_{$1}');
    return decodeHtml(withScripts);
};
const extractLatexBlocks = (rawText) => {
    const matches = [...rawText.matchAll(/\\\[(.*?)\\\]/gs)];
    return collectUniqueValues(matches.map((match) => match[1]));
};
const cleanHeadingText = (value) => normalizeWhitespace(value.replace(/^[^A-Za-z0-9]+/, ''));
const isLikelyFormula = (value) => {
    const compact = normalizeWhitespace(value);
    if (!compact)
        return false;
    // Các pattern LaTeX
    if (/\\(frac|sqrt|cdot|times|quad|text|begin|end|circ|pm|Rightarrow|Leftrightarrow|ge|le|ne|sum|prod|int|oint|binom|choose|lim|log|ln|sin|cos|tan)/.test(compact)) {
        return true;
    }
    // Căn bậc hai
    if (/(sqrt\(|sqrt\s)/i.test(compact)) {
        return true;
    }
    // Phân số
    if (/\d+\s*\/\s*\d+/.test(compact)) {
        return true;
    }
    // Biểu thức có dấu = và biến
    if (/[=^{}]|\|x\||\d\/.+/.test(compact) && /[a-zA-Z]/.test(compact)) {
        return true;
    }
    // Ma trận và hệ phương trình
    if (/(matrix|cases|array)/i.test(compact)) {
        return true;
    }
    // Ký hiệu toán học
    if (/[∑∏∫∂∇∈∉⊂⊆∩∪∀∃∞]/.test(compact)) {
        return true;
    }
    return false;
};
const extractInlineFormulaFallback = (rawText) => {
    return rawText
        .split(/\n+/)
        .map((line) => line.trim())
        .filter(isLikelyFormula);
};
const getArticleRoot = ($) => {
    const article = $('.entry-content[data-ast-blocks-layout]').first();
    if (article.length > 0)
        return article;
    const entryContent = $('.entry-content').first();
    if (entryContent.length > 0)
        return entryContent;
    return $('article').first();
};
// SỬA: Thêm Promise<> vào return type
const extractFormulas = async ($, pageTitle, pageUrl) => {
    const article = getArticleRoot($);
    // Khởi tạo records với kết quả từ các nguồn đặc thù
    const mathsIsFunFormulas = extractMathsIsFunFormulas($, pageTitle, pageUrl);
    const mathFormulaAtlasFormulas = extractMathFormulaAtlasFormulas($, pageTitle, pageUrl);
    let vietJackFormulas = [];
    if (pageUrl.includes('vietjack.com')) {
        vietJackFormulas = await extractVietJackFormulas($, pageTitle, pageUrl);
    }
    const records = [...mathsIsFunFormulas, ...mathFormulaAtlasFormulas, ...vietJackFormulas];
    const seen = new Set();
    const subjectSlug = getSubjectSlug(pageUrl);
    const subjectPath = getSubjectPath(pageUrl);
    let currentSection = '';
    let currentSubsection = '';
    const contentRoot = article.length > 0 ? article : $('body').first();
    // Đánh dấu các công thức đã có để tránh trùng lặp
    records.forEach(record => seen.add(record.latex));
    const pushFormula = (latex, source) => {
        if (seen.has(latex))
            return;
        seen.add(latex);
        records.push({
            latex,
            pageTitle,
            pageUrl,
            subjectSlug,
            subjectPath,
            section: currentSection || 'Uncategorized',
            subsection: currentSubsection,
            formulaName: '',
            source,
            indexInPage: records.length + 1,
        });
    };
    const pushNormalizedFormula = (value, source) => {
        if (!value)
            return;
        const normalized = normalizeFormulaInput(value);
        if (!normalized?.latex)
            return;
        pushFormula(normalized.latex, source);
    };
    const hasMathNodes = contentRoot.find('math, [data-mathml], [data-mathml-encoded]').length > 0 ||
        contentRoot.find('script[type^="math/tex"], .MathJax, mjx-container, .katex').length > 0;
    const allowInlineFallback = !hasMathNodes;
    // Xử lý các heading để cập nhật section context
    article.children().each((_, element) => {
        const tagName = element.tagName?.toLowerCase();
        if (!tagName)
            return;
        if (tagName === 'h2') {
            currentSection = cleanHeadingText($(element).text());
            currentSubsection = '';
            return;
        }
        if (tagName === 'h3') {
            const headingText = cleanHeadingText($(element).text());
            currentSubsection = headingText;
            return;
        }
        if (!['p', 'ul', 'ol'].includes(tagName)) {
            return;
        }
        const elementsToInspect = tagName === 'p' ? [element] : $(element).find('li').get();
        for (const child of elementsToInspect) {
            const rawHtml = $(child).html();
            if (!rawHtml)
                continue;
            const rawText = htmlToTextWithBreaks(rawHtml);
            const latexBlocks = extractLatexBlocks(rawText);
            if (latexBlocks.length > 0) {
                latexBlocks.forEach((latex) => pushFormula(latex, 'latex-block'));
                continue;
            }
            if (allowInlineFallback) {
                extractInlineFormulaFallback(rawText).forEach((candidate) => pushNormalizedFormula(candidate, 'formula-text-fallback'));
            }
        }
    });
    // Xử lý các thẻ math
    contentRoot.find('math').each((_, element) => {
        const annotation = $(element).find('annotation[encoding="application/x-tex"]').first();
        if (annotation.length > 0) {
            pushNormalizedFormula(annotation.text(), 'mathml-annotation');
            return;
        }
        const mathml = $.html(element);
        if (mathml && isMathmlMarkup(mathml)) {
            pushNormalizedFormula(mathml, 'mathml-to-latex');
        }
    });
    // Xử lý data-mathml attributes
    contentRoot.find('[data-mathml], [data-mathml-encoded], .MathJax_CHTML[data-mathml]').each((_, element) => {
        const raw = $(element).attr('data-mathml') ?? $(element).attr('data-mathml-encoded');
        if (!raw)
            return;
        const decoded = decodeHtml(raw).trim();
        if (!decoded)
            return;
        if (isMathmlMarkup(decoded)) {
            const mathml = decoded.startsWith('<math') ? decoded : `<math>${decoded}</math>`;
            pushNormalizedFormula(mathml, 'mathml-to-latex');
            return;
        }
        pushNormalizedFormula(decoded, 'latex-attribute');
    });
    // Xử lý MathJax containers
    contentRoot.find('.MathJax, .MathJax_Display, mjx-container').each((_, element) => {
        const mathmlAttr = $(element).attr('data-mathml');
        if (mathmlAttr) {
            pushNormalizedFormula(mathmlAttr, 'mathjax-data-mathml');
            return;
        }
        const innerMath = $(element).find('math').first();
        if (innerMath.length > 0) {
            const mathml = $.html(innerMath);
            pushNormalizedFormula(mathml, 'mathjax-math');
        }
    });
    // Fallback cho các trang không có công thức nào
    if (records.length === 0) {
        $('[data-tex], annotation[encoding="application/x-tex"], script[type^="math/tex"], .MathJax, .MathJax_Display')
            .each((_, element) => {
            const values = [
                $(element).attr('data-tex'),
                $(element).text(),
                $(element).html(),
            ];
            values.forEach((value) => pushNormalizedFormula(value, 'generic-math-fallback'));
        });
    }
    return records;
};
const isExampleContext = ($, element) => {
    // Kiểm tra text xung quanh element
    const parentText = $(element).parent().text().toLowerCase();
    const prevText = $(element).prev().text().toLowerCase();
    const nextText = $(element).next().text().toLowerCase();
    const siblingText = $(element).siblings().first().text().toLowerCase();
    // Các từ khóa chỉ ví dụ
    const exampleKeywords = [
        'ví dụ', 'vd', 'example', 'ex:', 'e.g',
        'chẳng hạn', 'như:', ':', 'tính:', 'tìm:'
    ];
    // Các từ khóa chỉ công thức (ưu tiên)
    const formulaKeywords = [
        'công thức', 'formula', 'định lý', 'theorem',
        'định nghĩa', 'definition', 'tính chất', 'property'
    ];
    // Kiểm tra nếu có từ khóa công thức thì ưu tiên giữ lại
    for (const keyword of formulaKeywords) {
        if (parentText.includes(keyword) || prevText.includes(keyword)) {
            return false; // Đây là công thức, không phải ví dụ
        }
    }
    // Kiểm tra nếu có từ khóa ví dụ
    for (const keyword of exampleKeywords) {
        if (prevText.includes(keyword) || siblingText.includes(keyword)) {
            return true; // Đây là ví dụ
        }
    }
    // Kiểm tra nếu nằm trong thẻ có class chứa "example"
    const parentClass = $(element).parent().attr('class')?.toLowerCase() || '';
    if (parentClass.includes('example') || parentClass.includes('vidu')) {
        return true;
    }
    // Kiểm tra nếu có số thứ tự ví dụ (VD1, VD2, Example 1, ...)
    if (/vd\s*\d+|example\s*\d+|ví dụ\s*\d+/i.test(prevText)) {
        return true;
    }
    return false;
};
const isFormulaInTable = ($, element) => {
    // Kiểm tra nếu công thức nằm trong bảng công thức (thường là công thức chính)
    const $table = $(element).closest('table');
    if ($table.length === 0)
        return false;
    const tableText = $table.text().toLowerCase();
    const tableClass = $table.attr('class')?.toLowerCase() || '';
    // Bảng công thức thường có các từ khóa
    if (tableClass.includes('formula') || tableClass.includes('congthuc')) {
        return true;
    }
    // Nếu bảng có cấu trúc 2 cột (công thức | mô tả)
    const rows = $table.find('tr');
    if (rows.length > 0) {
        const firstRowCells = rows.first().find('td, th');
        if (firstRowCells.length === 2) {
            const firstCellText = firstRowCells.eq(0).text().toLowerCase();
            if (firstCellText.includes('công thức') || firstCellText.includes('formula')) {
                return true;
            }
        }
    }
    return false;
};
const extractVietJackFormulas = async ($, pageTitle, pageUrl) => {
    const records = [];
    const subjectSlug = getSubjectSlug(pageUrl);
    const subjectPath = getSubjectPath(pageUrl);
    let currentSection = '';
    let currentSubsection = '';
    // Xử lý heading
    $('h2, h3, h4').each((_, heading) => {
        const tagName = heading.tagName?.toLowerCase();
        const headingText = cleanHeadingText($(heading).text());
        if (tagName === 'h2') {
            currentSection = headingText;
            currentSubsection = '';
        }
        else if (tagName === 'h3') {
            currentSubsection = headingText;
        }
    });
    // Tìm tất cả các thẻ span có id bắt đầu bằng MathJax
    $('span[id^="MathJax-Element-"], span.MathJax_CHTML, span.MathJax').each((_, element) => {
        // Lấy text hiển thị
        const displayText = $(element).text().trim();
        // Lọc các text có dấu = và có vẻ là công thức
        if (displayText && displayText.includes('=') && displayText.length > 3) {
            // Thay thế các ký tự đặc biệt
            let latex = displayText
                .replace(/log/g, '\\log')
                .replace(/ln/g, '\\ln')
                .replace(/sin/g, '\\sin')
                .replace(/cos/g, '\\cos')
                .replace(/tan/g, '\\tan')
                .replace(/cot/g, '\\cot')
                .replace(/⋅/g, '\\cdot')
                .replace(/×/g, '\\times')
                .replace(/∞/g, '\\infty')
                .replace(/√/g, '\\sqrt')
                .replace(/π/g, '\\pi')
                .replace(/α/g, '\\alpha')
                .replace(/β/g, '\\beta')
                .replace(/γ/g, '\\gamma')
                .replace(/Δ/g, '\\Delta');
            const normalized = normalizeFormulaInput(latex);
            if (normalized?.latex) {
                records.push({
                    latex: normalized.latex,
                    pageTitle,
                    pageUrl,
                    subjectSlug,
                    subjectPath,
                    section: currentSection || 'Uncategorized',
                    subsection: currentSubsection,
                    formulaName: '',
                    source: 'vietjack-text',
                    indexInPage: records.length + 1,
                });
            }
        }
    });
    // Nếu không tìm thấy, thử tìm trong các thẻ script
    if (records.length === 0) {
        $('script[type="math/tex"], script[type="math/tex; mode=display"]').each((_, element) => {
            const content = $(element).text().trim();
            if (content) {
                const normalized = normalizeFormulaInput(content);
                if (normalized?.latex) {
                    records.push({
                        latex: normalized.latex,
                        pageTitle,
                        pageUrl,
                        subjectSlug,
                        subjectPath,
                        section: currentSection || 'Uncategorized',
                        subsection: currentSubsection,
                        formulaName: '',
                        source: 'vietjack-script',
                        indexInPage: records.length + 1,
                    });
                }
            }
        });
    }
    console.log(`[vietjack] Extracted ${records.length} formulas from ${pageUrl}`);
    return records;
};
const extractVietJackLinks = ($, currentUrl) => {
    const links = [];
    // Tìm tất cả các link đến các bài viết công thức
    $('a[href*="/cong-thuc/"]').each((_, element) => {
        const href = $(element).attr('href');
        if (href) {
            const absoluteUrl = toAbsoluteUrl(href, currentUrl);
            if (absoluteUrl && absoluteUrl.includes('vietjack.com/cong-thuc/')) {
                links.push(absoluteUrl);
            }
        }
    });
    return links;
};
const isFormulaContent = (latex) => {
    // Các pattern thường xuất hiện trong ví dụ (số cụ thể)
    const examplePatterns = [
        /=\s*\d+/, // = số cụ thể
        /≈\s*\d+/, // ≈ số cụ thể
        /→\s*\d+/, // → số cụ thể
        /⇒\s*\d+/, // ⇒ số cụ thể
        /\\approx\s*\d+/, // \approx số
        /\\rightarrow\s*\d+/ // \rightarrow số
    ];
    // Các pattern thường xuất hiện trong công thức (biến số)
    const formulaPatterns = [
        /[a-z]\s*=\s*[a-z]/, // x = y
        /=\s*[a-z]/, // = biến
        /\\frac{[a-z]}{[a-z]}/, // phân số với biến
        /\\sum_[a-z]/, // tổng với biến
        /\\int_[a-z]/, // tích phân với biến
        /[a-z]\^[a-z0-9]/ // lũy thừa với biến
    ];
    // Nếu có pattern của ví dụ và không có pattern của công thức
    const hasExamplePattern = examplePatterns.some(pattern => pattern.test(latex));
    const hasFormulaPattern = formulaPatterns.some(pattern => pattern.test(latex));
    if (hasExamplePattern && !hasFormulaPattern) {
        return false; // Đây là ví dụ
    }
    // Nếu công thức chứa nhiều số hơn biến, có thể là ví dụ
    const numberCount = (latex.match(/\d+/g) || []).length;
    const variableCount = (latex.match(/[a-z](?![a-z])/g) || []).length;
    if (numberCount > variableCount * 2 && variableCount === 0) {
        return false; // Chỉ toàn số, có thể là ví dụ tính toán
    }
    return true;
};
const extractMathFormulaAtlasFormulas = ($, pageTitle, pageUrl) => {
    const records = [];
    const subjectSlug = getSubjectSlug(pageUrl);
    const subjectPath = getSubjectPath(pageUrl);
    let currentSection = '';
    let currentSubsection = '';
    // Xử lý heading
    $('h2, h3').each((_, heading) => {
        const tagName = heading.tagName?.toLowerCase();
        const headingText = cleanHeadingText($(heading).text());
        if (tagName === 'h2') {
            currentSection = headingText;
            currentSubsection = '';
        }
        else if (tagName === 'h3') {
            currentSubsection = headingText;
        }
    });
    // Xử lý các đoạn văn bản
    $('p, li, td').each((_, element) => {
        const text = $(element).text();
        // Tìm các công thức dạng: tên = biểu thức (có thể chứa \frac, \binom, v.v.)
        // Sửa regex để bắt cả các ký tự đặc biệt
        const formulaMatches = text.matchAll(/([A-Za-z()\s,|]+?)\s*=\s*([^=]+?)(?=\s*(?:[A-Za-z]|$|\(|\)|\{|\[|\\|\^))/g);
        for (const match of formulaMatches) {
            let rawFormula = `${match[1]}=${match[2]}`.trim();
            if (rawFormula.length > 5 && rawFormula.length < 300 && /[=]/.test(rawFormula)) {
                // Thay thế các ký tự đặc biệt
                rawFormula = rawFormula
                    .replace(/–/g, '-')
                    .replace(/…/g, '...')
                    .replace(/×/g, '\\times ')
                    .replace(/⋅/g, '\\cdot ')
                    .replace(/(\d+)\s*\/\s*(\d+)/g, '\\frac{$1}{$2}'); // Thêm xử lý phân số
                const normalized = normalizeFormulaInput(rawFormula);
                if (normalized?.latex) {
                    records.push({
                        latex: normalized.latex,
                        pageTitle,
                        pageUrl,
                        subjectSlug,
                        subjectPath,
                        section: currentSection || 'Uncategorized',
                        subsection: currentSubsection,
                        formulaName: match[1].trim(),
                        source: 'mathformulaatlas-text',
                        indexInPage: records.length + 1,
                    });
                }
            }
        }
        // Xử lý các công thức có dấu \ (LaTeX thuần) - mở rộng regex
        const latexMatches = text.matchAll(/\\(frac|binom|sum|prod|int|sqrt|choose|lim|log|ln|sin|cos|tan)\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}/g);
        for (const match of latexMatches) {
            const normalized = normalizeFormulaInput(match[0]);
            if (normalized?.latex) {
                records.push({
                    latex: normalized.latex,
                    pageTitle,
                    pageUrl,
                    subjectSlug,
                    subjectPath,
                    section: currentSection || 'Uncategorized',
                    subsection: currentSubsection,
                    formulaName: '',
                    source: 'mathformulaatlas-latex',
                    indexInPage: records.length + 1,
                });
            }
        }
        // Bổ sung: xử lý các công thức dạng (n choose k)
        const chooseMatches = text.matchAll(/\(([^)]+)\s+choose\s+([^)]+)\)/gi);
        for (const match of chooseMatches) {
            const latexFormula = `\\binom{${match[1].trim()}}{${match[2].trim()}}`;
            const normalized = normalizeFormulaInput(latexFormula);
            if (normalized?.latex) {
                records.push({
                    latex: normalized.latex,
                    pageTitle,
                    pageUrl,
                    subjectSlug,
                    subjectPath,
                    section: currentSection || 'Uncategorized',
                    subsection: currentSubsection,
                    formulaName: '',
                    source: 'mathformulaatlas-choose',
                    indexInPage: records.length + 1,
                });
            }
        }
    });
    console.log(`[mathformulaatlas] Extracted ${records.length} formulas from ${pageUrl}`);
    return records;
};
const extractFormulaSheetListName = (value) => {
    const match = value.match(/\"([^\"]+)\"/);
    return match ? match[1].trim() : '';
};
const extractFormulaSheetFormulas = ($, pageTitle, pageUrl) => {
    const records = [];
    const subjectSlug = 'formulasheet';
    const subjectPath = '/formulasheet/';
    $('.resultCont.formula').each((_, element) => {
        const title = normalizeWhitespace($(element).find('.resultTitle').first().text());
        const infoText = normalizeWhitespace($(element).find('.content-info').first().text());
        const listName = extractFormulaSheetListName(infoText);
        const latexRaw = $(element).find('pre.resultsSrc').first().text();
        const normalized = normalizeFormulaInput(latexRaw);
        if (!normalized?.latex)
            return;
        records.push({
            latex: normalized.latex,
            pageTitle,
            pageUrl,
            subjectSlug,
            subjectPath,
            section: listName || 'FormulaSheet',
            subsection: title || '',
            formulaName: '',
            source: 'formulasheet-latex',
            indexInPage: records.length + 1,
        });
    });
    return records;
};
const toSlugPart = (value) => value
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .trim();
const getBasePageSlug = (pageUrl, pageTitle) => {
    const segments = getPathSegments(pageUrl);
    const lastSegment = segments.at(-1);
    if (lastSegment) {
        return toSlugPart(lastSegment) || 'page';
    }
    return toSlugPart(pageTitle) || 'page';
};
const ensureCleanDirectory = (directoryPath) => {
    fs_1.default.mkdirSync(directoryPath, { recursive: true });
    const preservePattern = /^datasheet.*\.json$/i;
    for (const entry of fs_1.default.readdirSync(directoryPath)) {
        if (preservePattern.test(entry))
            continue;
        fs_1.default.rmSync(path_1.default.join(directoryPath, entry), { recursive: true, force: true });
    }
};
const toCommentValue = (value) => normalizeWhitespace(value || '').replace(/\r?\n/g, ' ');
const buildPageSlugMap = (pages) => {
    const slugMap = new Map();
    const usedSlugs = new Set();
    for (const page of pages) {
        const segments = getPathSegments(page.url);
        const baseSlug = getBasePageSlug(page.url, page.title);
        const candidates = [
            baseSlug,
            toSlugPart(`${segments.at(-2) ?? ''}-${baseSlug}`),
            toSlugPart(segments.slice(-3).join('-')),
        ].filter(Boolean);
        let finalSlug = candidates.find((candidate) => !usedSlugs.has(candidate));
        if (!finalSlug) {
            let suffix = 2;
            finalSlug = `${baseSlug}-${suffix}`;
            while (usedSlugs.has(finalSlug)) {
                suffix += 1;
                finalSlug = `${baseSlug}-${suffix}`;
            }
        }
        usedSlugs.add(finalSlug);
        slugMap.set(page.url, finalSlug);
    }
    return slugMap;
};
const finalizePages = (pages) => {
    const slugMap = buildPageSlugMap(pages);
    let globalIndex = 1;
    return pages.map((page) => {
        const pageSlug = slugMap.get(page.url) ?? getBasePageSlug(page.url, page.title);
        const outputFile = `${pageSlug}.tex`;
        return {
            title: page.title,
            url: page.url,
            pageSlug,
            outputFile,
            subjectSlug: page.subjectSlug,
            subjectPath: page.subjectPath,
            formulas: page.formulas.map((formula) => ({
                ...formula,
                pageSlug,
                outputFile,
                formulaId: `${pageSlug}-${String(formula.indexInPage).padStart(3, '0')}`,
                indexGlobal: globalIndex++,
            })),
        };
    });
};
const writePageFormulaFile = (outputDir, pageResult) => {
    const content = [
        `% dataset: math-formula-atlas`,
        `% page_slug: ${pageResult.pageSlug}`,
        `% page_title: ${toCommentValue(pageResult.title)}`,
        `% page_url: ${pageResult.url}`,
        `% subject_slug: ${pageResult.subjectSlug}`,
        `% subject_path: ${pageResult.subjectPath}`,
        `% formula_count: ${pageResult.formulas.length}`,
        ...pageResult.formulas.map((formula) => {
            const parts = [
                `% formula_record_start`,
                `% formula_id: ${formula.formulaId}`,
                `% index_global: ${formula.indexGlobal}`,
                `% index_in_page: ${formula.indexInPage}`,
                `% section: ${toCommentValue(formula.section)}`,
                `% subsection: ${toCommentValue(formula.subsection || 'none')}`,
                `% formula_name: ${toCommentValue(formula.formulaName || '')}`,
                `% source: ${formula.source}`,
                ...(formula.formulaName ? [`\\textbf{Label: ${toCommentValue(formula.formulaName)}}`] : []),
                `\\[${formula.latex}\\]`,
                `% formula_record_end`,
            ];
            return parts.join('\n');
        }),
    ].join('\n\n');
    fs_1.default.writeFileSync(path_1.default.join(outputDir, pageResult.outputFile), content, 'utf8');
};
const writeSummaryFiles = (outputDir, pages, options) => {
    const allFormulas = pages.flatMap((page) => page.formulas);
    const generatedAt = new Date().toISOString();
    const latexDocument = allFormulas
        .map((formula) => [
        `% formula_record_start`,
        `% formula_id: ${formula.formulaId}`,
        `% page_slug: ${formula.pageSlug}`,
        `% page_title: ${toCommentValue(formula.pageTitle)}`,
        `% page_url: ${formula.pageUrl}`,
        `% subject_slug: ${formula.subjectSlug}`,
        `% subject_path: ${formula.subjectPath}`,
        `% section: ${toCommentValue(formula.section)}`,
        `% subsection: ${toCommentValue(formula.subsection || 'none')}`,
        `% formula_name: ${toCommentValue(formula.formulaName || '')}`,
        `% source: ${formula.source}`,
        `% index_global: ${formula.indexGlobal}`,
        `% index_in_page: ${formula.indexInPage}`,
        ...(formula.formulaName ? [`\\textbf{Label: ${toCommentValue(formula.formulaName)}}`] : []),
        `\\[${formula.latex}\\]`,
        `% formula_record_end`,
    ].join('\n'))
        .join('\n\n');
    const summary = {
        dataset: 'math-formula-atlas',
        generatedAt,
        crawl: {
            startUrl: options.startUrl,
            scopePathPrefix: options.scopePathPrefix,
            maxPages: options.maxPages,
            outputDir: options.outputDir,
            totalPages: pages.length,
            totalFormulas: allFormulas.length,
        },
        pages: pages.map((page) => ({
            pageSlug: page.pageSlug,
            title: page.title,
            url: page.url,
            outputFile: page.outputFile,
            subjectSlug: page.subjectSlug,
            subjectPath: page.subjectPath,
            formulaCount: page.formulas.length,
        })),
        formulas: allFormulas,
    };
    const jsonlDocument = allFormulas.map((formula) => JSON.stringify(formula)).join('\n');
    const datasetHeader = [
        `% dataset: math-formula-atlas`,
        `% generated_at: ${generatedAt}`,
        `% start_url: ${options.startUrl}`,
        `% scope_path_prefix: ${options.scopePathPrefix}`,
        `% total_pages: ${pages.length}`,
        `% total_formulas: ${allFormulas.length}`,
    ].join('\n');
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'dataset.tex'), `${datasetHeader}\n\n${latexDocument}`, 'utf8');
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'dataset.json'), JSON.stringify(summary, null, 2), 'utf8');
    fs_1.default.writeFileSync(path_1.default.join(outputDir, 'dataset.jsonl'), jsonlDocument, 'utf8');
};
const extractNextLinks = ($, currentUrl, startHost, scopePathPrefix, ignoredPathFragments) => {
    const containers = [getArticleRoot($), $('main').first(), $('body').first()].filter((node) => node.length > 0);
    const collectedLinks = new Set();
    for (const container of containers) {
        container
            .find('a[href]')
            .map((_, element) => $(element).attr('href'))
            .get()
            .map((href) => (href ? toAbsoluteUrl(href, currentUrl) : null))
            .filter((href) => Boolean(href))
            .filter((href) => {
            // Chỉ lấy các link vietjack
            if (!href.includes('vietjack.com'))
                return false;
            return isAllowedPage(href, startHost, scopePathPrefix, ignoredPathFragments);
        })
            .forEach((href) => collectedLinks.add(href));
    }
    return [...collectedLinks];
};
const crawlFormulaSheetPage = async (page, url) => {
    try {
        await page.goto(url, { waitUntil: 'networkidle2' });
        await page.waitForSelector('.resultCont.formula', { timeout: 20_000 });
    }
    catch {
        console.error('skip', url, 'formulasheet-timeout');
        return null;
    }
    const html = await page.content();
    const $ = (0, cheerio_1.load)(html);
    const pageTitle = normalizeWhitespace($('title').first().text()) || 'FormulaSheet';
    const formulas = extractFormulaSheetFormulas($, pageTitle, url);
    console.log('formulasheet', url, 'formulas', formulas.length);
    return {
        title: pageTitle,
        url,
        subjectSlug: 'formulasheet',
        subjectPath: '/formulasheet/',
        formulas,
        nextLinks: [],
    };
};
const createBrowser = async () => puppeteer_1.default.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
});
const createPage = async (browser) => {
    const page = await browser.newPage();
    await page.setUserAgent(USER_AGENT);
    await page.setExtraHTTPHeaders({
        'accept-language': 'en-US,en;q=0.9',
    });
    page.setDefaultNavigationTimeout(60_000);
    return page;
};
const crawlPage = async (page, url, options) => {
    let response;
    try {
        response = await page.goto(url, { waitUntil: 'networkidle2' });
    }
    catch (error) {
        console.error('skip', url, 'navigation-failed');
        return null;
    }
    if (!response || !response.ok()) {
        console.error('skip', url, response?.status() ?? 'no-response');
        return null;
    }
    const html = await page.content();
    const $ = (0, cheerio_1.load)(html);
    const pageTitle = normalizeWhitespace($('title').first().text()) || url;
    // THÊM await vì extractFormulas bây giờ là async
    const formulas = await extractFormulas($, pageTitle, url);
    const nextLinks = extractNextLinks($, url, new URL(options.startUrl).host, options.scopePathPrefix, options.ignoredPathFragments);
    console.log('page', url, 'formulas', formulas.length);
    return {
        title: pageTitle,
        url,
        subjectSlug: getSubjectSlug(url),
        subjectPath: getSubjectPath(url),
        formulas, // Đã là ExtractedFormulaRecord[] không phải Promise
        nextLinks,
    };
};
// Nếu bạn muốn dùng crawlVietJackPage, cần sửa lại:
const crawlVietJackPage = async (page, url) => {
    try {
        await page.goto(url, { waitUntil: 'networkidle2' });
        // Bỏ phần waitForFunction với MathJax vì có thể không cần
        // Hoặc dùng cách an toàn hơn:
        try {
            await page.waitForFunction(() => {
                return document.querySelectorAll('span[id^="MathJax-Element-"]').length > 0;
            }, { timeout: 10000 });
        }
        catch {
            console.log('No MathJax elements found');
        }
        const html = await page.content();
        const $ = (0, cheerio_1.load)(html);
        const pageTitle = normalizeWhitespace($('title').first().text()) || url;
        const formulas = await extractVietJackFormulas($, pageTitle, url);
        const nextLinks = extractNextLinksFromPage($, url); // Cần định nghĩa hàm này
        return {
            title: pageTitle,
            url,
            subjectSlug: 'vietjack',
            subjectPath: '/cong-thuc/',
            formulas,
            nextLinks,
        };
    }
    catch (error) {
        console.error('Error crawling', url, error);
        return null;
    }
};
// Định nghĩa extractNextLinksFromPage nếu cần
const extractNextLinksFromPage = ($, currentUrl) => {
    const links = [];
    $('a[href*="/cong-thuc/"]').each((_, element) => {
        const href = $(element).attr('href');
        if (href) {
            const absoluteUrl = toAbsoluteUrl(href, currentUrl);
            if (absoluteUrl && absoluteUrl.includes('vietjack.com')) {
                links.push(absoluteUrl);
            }
        }
    });
    return links;
};
const extractVietJackFromText = ($, pageTitle, pageUrl) => {
    const records = [];
    const subjectSlug = getSubjectSlug(pageUrl);
    const subjectPath = getSubjectPath(pageUrl);
    // Tìm tất cả các thẻ span có id bắt đầu bằng MathJax
    $('span[id^="MathJax-Element-"]').each((_, element) => {
        // Lấy text hiển thị
        const displayText = $(element).text().trim();
        // Lọc các text có dấu = và có vẻ là công thức
        if (displayText && displayText.includes('=') && displayText.length > 3) {
            // Thay thế các ký tự đặc biệt
            let latex = displayText
                .replace(/log/g, '\\log')
                .replace(/⋅/g, '\\cdot')
                .replace(/×/g, '\\times')
                .replace(/∞/g, '\\infty')
                .replace(/√/g, '\\sqrt');
            const normalized = normalizeFormulaInput(latex);
            if (normalized?.latex) {
                records.push({
                    latex: normalized.latex,
                    pageTitle,
                    pageUrl,
                    subjectSlug,
                    subjectPath,
                    section: 'Uncategorized',
                    subsection: '',
                    formulaName: '',
                    source: 'vietjack-text',
                    indexInPage: records.length + 1,
                });
            }
        }
    });
    return records;
};
const crawlSite = async (options) => {
    ensureCleanDirectory(options.outputDir);
    const browser = await createBrowser();
    const page = await createPage(browser);
    // Chỉ crawl vietjack URLs
    const queue = Array.from(new Set([options.startUrl, ...(options.seedUrls ?? [])].filter(Boolean)));
    const seen = new Set();
    const pages = [];
    try {
        while (queue.length > 0 && seen.size < options.maxPages) {
            const currentUrl = queue.shift();
            if (!currentUrl || seen.has(currentUrl)) {
                continue;
            }
            // Chỉ crawl nếu URL là vietjack
            if (!currentUrl.includes('vietjack.com')) {
                continue;
            }
            seen.add(currentUrl);
            const pageResult = await crawlPage(page, currentUrl, options);
            if (!pageResult) {
                continue;
            }
            pages.push(pageResult);
            for (const nextLink of pageResult.nextLinks) {
                // Chỉ thêm các link vietjack vào queue
                if (!nextLink.includes('vietjack.com')) {
                    continue;
                }
                if (seen.has(nextLink) || queue.includes(nextLink)) {
                    continue;
                }
                queue.push(nextLink);
            }
        }
        // Bỏ formulaSheetPages nếu không cần
        // const formulaSheetPages: PageResult[] = [];
        // ... 
    }
    finally {
        await browser.close();
    }
    const finalizedPages = finalizePages(pages);
    finalizedPages.forEach((pageResult) => writePageFormulaFile(options.outputDir, pageResult));
    writeSummaryFiles(options.outputDir, finalizedPages, options);
    console.log('done', {
        pages: finalizedPages.length,
        formulas: finalizedPages.reduce((sum, pageResult) => sum + pageResult.formulas.length, 0),
        outputDir: options.outputDir,
        scopePathPrefix: options.scopePathPrefix,
    });
};
const isDuplicateContent = (url) => {
    // Loại bỏ các tham số không cần thiết
    const cleanUrl = url.split('?')[0].split('#')[0];
    // Các pattern không cần crawl
    const excludePatterns = [
        /\/bai-tap\//,
        /\/hoi-dap\//,
        /\/de-kiem-tra\//,
        /\/thi-online\//
    ];
    return excludePatterns.some(pattern => pattern.test(cleanUrl));
};
const startUrl = 'https://www.vietjack.com/cong-thuc/cac-cong-thuc-cong-tru-nhan-chia-so-huu-ti-sm.jsp';
const seedUrls = [
    'https://www.vietjack.com/cong-thuc/'
];
const defaultFormulaSheetUrls = [
    'https://formulasheet.com/#q|l|1228',
    'https://formulasheet.com/#q|l|1255',
    'https://formulasheet.com/#q|l|6084',
    'https://formulasheet.com/#q|l|4981',
    'https://formulasheet.com/#q|l|4989',
    'https://formulasheet.com/#q|l|4982',
    'https://formulasheet.com/#q|l|1022',
    'https://formulasheet.com/#q|l|1227',
    'https://formulasheet.com/#q|l|1245',
    'https://formulasheet.com/#q|l|1250',
    'https://formulasheet.com/#q|l|1722',
    'https://formulasheet.com/#q|l|1271',
    'https://formulasheet.com/#q|l|1250',
    'https://formulasheet.com/#q|l|1245',
    'https://formulasheet.com/#q|l|1252',
    'https://formulasheet.com/#q|l|4988',
    'https://formulasheet.com/#q|l|1229',
    'https://formulasheet.com/#q|l|1722'
];
const envFormulaSheetUrls = (process.env.CRAWL_FORMULASHEET_URLS ?? '')
    .split(',')
    .map((value) => value.trim())
    .filter(Boolean);
const formulaSheetUrls = [...defaultFormulaSheetUrls, ...envFormulaSheetUrls];
void crawlSite({
    startUrl: 'https://www.vietjack.com/cong-thuc/',
    seedUrls: [
        'https://www.vietjack.com/cong-thuc/cac-cong-thuc-cong-tru-nhan-chia-so-huu-ti-sm.jsp',
        'https://www.vietjack.com/cong-thuc/cac-cong-thuc-luy-thua-voi-so-mu-tu-nhien-sm.jsp',
        'https://www.vietjack.com/cong-thuc/cong-thuc-tinh-dien-tich-the-tich-hinh-hop-chu-nhat-hinh-sm.jsp',
        'https://www.vietjack.com/cong-thuc/cong-thuc-tinh-dien-tich-va-the-tich-cua-hinh-lang-sm.jsp',
        'https://www.vietjack.com/cong-thuc/cong-thuc-toan-lop-7-hoc-ki-1.jsp',
        'https://www.vietjack.com/cong-thuc/cong-thuc-luong-giac-cua-hai-goc-phu-nhau-bu-nhau-sm.jsp',
        'https://www.vietjack.com/cong-thuc/cong-thuc-doi-co-so-logarit-t11sm.jsp'
    ],
    formulaSheetUrls: [], // Bỏ formulaSheetUrls nếu không cần
    maxPages: Number(process.env.CRAWL_MAX_PAGES ?? '50'),
    outputDir: process.env.CRAWL_OUTPUT_DIR ?? path_1.default.join(process.cwd(), 'formulas'),
    scopePathPrefix: '/cong-thuc/', // Chỉ crawl trong /cong-thuc/
    ignoredPathFragments: [
        '/wp-', '/feed', '/tag/', '/category/',
        '/privacy-policy', '/contact', '/about',
        '/blog', '/comments', '/user', '/login',
        '/signup', '/search', '/pdf', '/download',
        '/cdn-cgi', '/wp-content', '/author',
        '/lien-he', '/gioi-thieu', // Thêm các từ khóa vietjack
    ],
});
