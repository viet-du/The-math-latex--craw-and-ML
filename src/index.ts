import { load, type CheerioAPI } from 'cheerio';
import { MathMLToLaTeX } from 'mathml-to-latex';
import puppeteer, { type Browser, type Page } from 'puppeteer';
import fs from 'fs';
import path from 'path';

type CrawlOptions = {
    startUrl: string;
    seedUrls?: string[];
    formulaSheetUrls?: string[];
    maxPages: number;
    outputDir: string;
    scopePathPrefix: string;
    ignoredPathFragments: string[];
};

type ExtractedFormulaRecord = {
    latex: string;
    pageTitle: string;
    pageUrl: string;
    subjectSlug: string;
    subjectPath: string;
    section: string;
    subsection: string;
    formulaName: string;
    imagePath?: string;
    source: string;
    indexInPage: number;
};

type FormulaRecord = ExtractedFormulaRecord & {
    formulaId: string;
    pageSlug: string;
    outputFile: string;
    indexGlobal: number;
};

type PageResult = {
    title: string;
    url: string;
    subjectSlug: string;
    subjectPath: string;
    formulas: ExtractedFormulaRecord[];
    nextLinks: string[];
};

type FinalizedPageResult = {
    title: string;
    url: string;
    pageSlug: string;
    outputFile: string;
    subjectSlug: string;
    subjectPath: string;
    formulas: FormulaRecord[];
};

const USER_AGENT =
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36';

const normalizeWhitespace = (value: string) => value.replace(/\s+/g, ' ').trim();

const normalizePathname = (value: string) => {
    const normalized = value.replace(/\/+/g, '/');
    if (!normalized || normalized === '/') return '/';
    return normalized.endsWith('/') ? normalized : `${normalized}/`;
};

const decodeHtml = (value: string) => load(`<div>${value}</div>`)('div').text();

const replaceLatexLikeSymbols = (value: string) =>
    value
        .replace(/⋅/g, '\\cdot ')
        .replace(/×/g, '\\times ')
        .replace(/≤/g, '\\leq ')
        .replace(/≥/g, '\\geq ')
        .replace(/≠/g, '\\ne ')
        .replace(/∞/g, '\\infty ')
        .replace(/∑/g, '\\sum ')
        .replace(/∏/g, '\\prod ')
        .replace(/∫/g, '\\int ')
        .replace(/√/g, '\\sqrt{}')
        .replace(/±/g, '\\pm ')
        .replace(/π/g, '\\pi ')
        .replace(/α/g, '\\alpha ')
        .replace(/β/g, '\\beta ')
        .replace(/γ/g, '\\gamma ')
        .replace(/Δ/g, '\\Delta ')
        .replace(/λ/g, '\\lambda ')
        .replace(/μ/g, '\\mu ')
        .replace(/σ/g, '\\sigma ')
        .replace(/φ/g, '\\phi ')
        .replace(/ω/g, '\\omega ');

const stripMathDelimiters = (value: string) => value.replace(/^\\\[\s*|\s*\\\]$/g, '');
const extractMathsIsFunFormulas = ($: CheerioAPI, pageTitle: string, pageUrl: string): ExtractedFormulaRecord[] => {
    const records: ExtractedFormulaRecord[] = [];
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
            } else {
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
                } else if (headingTag === 'h3') {
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
                            } else if (headingTag === 'h3') {
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
const isMathmlMarkup = (value: string) =>
    /<(math|mrow|mi|mn|mo|msup|msub|mfrac|msqrt|mroot|mtable|mtr|mtd|mfenced|mover|munder|munderover|msubsup|mmultiscripts)\b/i.test(
        value,
    );

type FormulaType = 'latex' | 'mathml' | 'text';

const detectFormulaType = (input: string): FormulaType => {
    if (input.includes('\\') || input.includes('$')) return 'latex';
    if (isMathmlMarkup(input)) return 'mathml';
    return 'text';
};

const normalizeImplicitPowers = (value: string) => {
    const superscriptMap: Record<string, string> = {
        '⁰': '0',
        '¹': '1',
        '²': '2',
        '³': '3',
        '⁴': '4',
        '⁵': '5',
        '⁶': '6',
        '⁷': '7',
        '⁸': '8',
        '⁹': '9',
    };
    const functionNames = new Set(['sin', 'cos', 'tan', 'sec', 'csc', 'cot', 'log', 'ln', 'exp']);

    const withUnicodeSuperscripts = value.replace(
        /([A-Za-z])([⁰¹²³⁴⁵⁶⁷⁸⁹])/g,
        (_match, letter: string, superscript: string) => `${letter}^{${superscriptMap[superscript] ?? superscript}}`,
    );

    return withUnicodeSuperscripts.replace(
        /([A-Za-z])([2-9])(?!\d)/g,
        (match, letter: string, digit: string, offset: number, source: string) => {
            const prefix = source.slice(0, offset + 1);
            const currentWord = prefix.match(/[A-Za-z]+$/)?.[0]?.toLowerCase() ?? '';
            if (currentWord.length > 1 && functionNames.has(currentWord)) {
                return match;
            }
            return `${letter}^{${digit}}`;
        },
    );
};

const textToLatex = (text: string): string =>
    normalizeImplicitPowers(
        text
            .replace(/sqrt\((.*?)\)/g, '\\\\sqrt{$1}')
            .replace(/(\d+)\s*\/\s*(\d+)/g, '\\\\frac{$1}{$2}')
            .replace(/\^(\d+)/g, '^{$1}')
            .replace(/\*/g, '\\\\cdot '),
    );

const normalizeVectorNotation = (value: string) =>
    value.replace(/([A-Za-z\u00C0-\u024F\u0370-\u03FF])\u20D7/g, '\\\\vec{$1}');

const normalizeLatex = (value: string) => {
    const decoded = decodeHtml(value)
        .replace(/\r/g, '')
        .replace(/\$+/g, '')
        .replace(/\\displaystyle/g, '')
        .replace(/&nbsp;/g, ' ')
        .replace(/\u00A0/g, ' ')
        .replace(/[–—−]/g, '-');

    const withSymbols = replaceLatexLikeSymbols(stripMathDelimiters(normalizeVectorNotation(decoded)));

    return withSymbols
        .replace(/\\\s+(?=[^a-zA-Z])/g, '\\\\ ')
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
        .join(' ')
        .replace(/\s+/g, ' ')
        .trim();
};

const normalizeFormulaInput = (input: string) => {
    const type = detectFormulaType(input);

    try {
        if (type === 'latex') {
            const latex = normalizeLatex(input);
            return latex ? { latex, type } : null;
        }

        if (type === 'mathml') {
            const latex = normalizeLatex(MathMLToLaTeX.convert(input));
            return latex ? { latex, type } : null;
        }

        const latex = normalizeLatex(textToLatex(input));
        return latex ? { latex, type } : null;
    } catch {
        return null;
    }
};

const toAbsoluteUrl = (link: string, currentUrl: string) => {
    try {
        const absoluteUrl = new URL(link, currentUrl);
        absoluteUrl.hash = '';
        return absoluteUrl.toString();
    } catch {
        return null;
    }
};

const getPathSegments = (pageUrl: string) => new URL(pageUrl).pathname.split('/').filter(Boolean);

const deriveScopePathPrefix = (pageUrl: string) => {
    const segments = getPathSegments(pageUrl);

    if (segments[0] === 'subjects' && segments.length >= 2) {
        return normalizePathname(`/${segments.slice(0, 2).join('/')}`);
    }

    if (segments.length <= 1) {
        return normalizePathname(new URL(pageUrl).pathname);
    }

    return normalizePathname(`/${segments.slice(0, -1).join('/')}`);
};

const getSubjectSlug = (pageUrl: string) => {
    const segments = getPathSegments(pageUrl);
    if (segments[0] === 'subjects' && segments.length >= 2) {
        return segments[1];
    }

    return segments[0] ?? 'general';
};

const getSubjectPath = (pageUrl: string) => deriveScopePathPrefix(pageUrl);

const isAllowedPage = (
    rawUrl: string,
    startHost: string,
    scopePathPrefix: string,
    ignoredPathFragments: string[],
) => {
    try {
        const url = new URL(rawUrl);
        if (url.host !== startHost) return false;
        if (!['http:', 'https:'].includes(url.protocol)) return false;
        if (ignoredPathFragments.some((fragment) => rawUrl.includes(fragment) || url.pathname.includes(fragment))) {
            return false;
        }
        if (!url.pathname || url.pathname === '/') return false;
        if (/\.(png|jpg|jpeg|gif|webp|svg|pdf|xml)$/i.test(url.pathname)) return false;
        if (!normalizePathname(url.pathname).startsWith(scopePathPrefix)) return false;

        return true;
    } catch {
        return false;
    }
};

const collectUniqueValues = (values: Array<string | undefined | null>) => {
    const seen = new Set<string>();
    const results: string[] = [];

    for (const value of values) {
        if (!value) continue;
        const latex = normalizeLatex(value);
        if (!latex) continue;
        if (seen.has(latex)) continue;
        seen.add(latex);
        results.push(latex);
    }

    return results;
};

const htmlToTextWithBreaks = (html: string) => {
    const withLineBreaks = html.replace(/<br\s*\/?>/gi, '\n');
    const withScripts = withLineBreaks
        .replace(/<sup[^>]*>([\s\S]*?)<\/sup>/gi, '^{$1}')
        .replace(/<sub[^>]*>([\s\S]*?)<\/sub>/gi, '_{$1}');
    return decodeHtml(withScripts);
};

const extractLatexBlocks = (rawText: string) => {
    const matches = [...rawText.matchAll(/\\\[(.*?)\\\]/gs)];
    return collectUniqueValues(matches.map((match) => match[1]));
};

const cleanHeadingText = (value: string) => normalizeWhitespace(value.replace(/^[^A-Za-z0-9]+/, ''));

const isLikelyFormula = (value: string) => {
    const compact = normalizeWhitespace(value);
    if (!compact) return false;
    if (/\\(frac|sqrt|cdot|times|quad|text|begin|end|circ|pm|Rightarrow|ge|le|ne)/.test(compact)) {
        return true;
    }
    if (/(sqrt\(|sqrt\s)/i.test(compact)) {
        return true;
    }
    if (/\d+\s*\/\s*\d+/.test(compact)) {
        return true;
    }
    if (/[=^{}]|\|x\||\d\/.+/.test(compact) && /[a-zA-Z]/.test(compact)) {
        return true;
    }
    return false;
};

const extractInlineFormulaFallback = (rawText: string) => {
    return rawText
        .split(/\n+/)
        .map((line) => line.trim())
        .filter(isLikelyFormula);
};

const getArticleRoot = ($: CheerioAPI) => {
    const article = $('.entry-content[data-ast-blocks-layout]').first();
    if (article.length > 0) return article;

    const entryContent = $('.entry-content').first();
    if (entryContent.length > 0) return entryContent;

    return $('article').first();
};

const extractFormulas = ($: CheerioAPI, pageTitle: string, pageUrl: string): ExtractedFormulaRecord[] => {
    const article = getArticleRoot($);
    
    // Khởi tạo records với kết quả từ mathsisfun
    const mathsIsFunFormulas = extractMathsIsFunFormulas($, pageTitle, pageUrl);
    const records: ExtractedFormulaRecord[] = [...mathsIsFunFormulas];
    const seen = new Set<string>();
    const subjectSlug = getSubjectSlug(pageUrl);
    const subjectPath = getSubjectPath(pageUrl);
    let currentSection = '';
    let currentSubsection = '';
    const contentRoot = article.length > 0 ? article : $('body').first();

    // Đánh dấu các công thức đã có từ mathsisfun để tránh trùng lặp
    records.forEach(record => seen.add(record.latex));

    const pushFormula = (latex: string, source: string) => {
        if (seen.has(latex)) return;
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

    const pushNormalizedFormula = (value: string | null | undefined, source: string) => {
        if (!value) return;
        const normalized = normalizeFormulaInput(value);
        if (!normalized?.latex) return;
        pushFormula(normalized.latex, source);
    };

    const hasMathNodes =
        contentRoot.find('math, [data-mathml], [data-mathml-encoded]').length > 0 ||
        contentRoot.find('script[type^="math/tex"], .MathJax, mjx-container, .katex').length > 0;
    const allowInlineFallback = !hasMathNodes;

    // Xử lý các heading để cập nhật section context
    article.children().each((_, element) => {
        const tagName = element.tagName?.toLowerCase();

        if (!tagName) return;

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
            if (!rawHtml) continue;

            const rawText = htmlToTextWithBreaks(rawHtml);
            const latexBlocks = extractLatexBlocks(rawText);

            if (latexBlocks.length > 0) {
                latexBlocks.forEach((latex) => pushFormula(latex, 'latex-block'));
                continue;
            }

            if (allowInlineFallback) {
                extractInlineFormulaFallback(rawText).forEach((candidate) =>
                    pushNormalizedFormula(candidate, 'formula-text-fallback'),
                );
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
    contentRoot.find('[data-mathml], [data-mathml-encoded]').each((_, element) => {
        const raw = $(element).attr('data-mathml') ?? $(element).attr('data-mathml-encoded');
        if (!raw) return;

        const decoded = decodeHtml(raw).trim();
        if (!decoded) return;

        if (isMathmlMarkup(decoded)) {
            const mathml = decoded.startsWith('<math') ? decoded : `<math>${decoded}</math>`;
            pushNormalizedFormula(mathml, 'mathml-to-latex');
            return;
        }

        pushNormalizedFormula(decoded, 'latex-attribute');
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
const extractFormulaSheetListName = (value: string) => {
    const match = value.match(/\"([^\"]+)\"/);
    return match ? match[1].trim() : '';
};

const extractFormulaSheetFormulas = ($: CheerioAPI, pageTitle: string, pageUrl: string): ExtractedFormulaRecord[] => {
    const records: ExtractedFormulaRecord[] = [];
    const subjectSlug = 'formulasheet';
    const subjectPath = '/formulasheet/';

    $('.resultCont.formula').each((_, element) => {
        const title = normalizeWhitespace($(element).find('.resultTitle').first().text());
        const infoText = normalizeWhitespace($(element).find('.content-info').first().text());
        const listName = extractFormulaSheetListName(infoText);
        const latexRaw = $(element).find('pre.resultsSrc').first().text();

        const normalized = normalizeFormulaInput(latexRaw);
        if (!normalized?.latex) return;

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


const toSlugPart = (value: string) =>
    value
        .toLowerCase()
        .normalize('NFKD')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .trim();

const getBasePageSlug = (pageUrl: string, pageTitle: string) => {
    const segments = getPathSegments(pageUrl);
    const lastSegment = segments.at(-1);

    if (lastSegment) {
        return toSlugPart(lastSegment) || 'page';
    }

    return toSlugPart(pageTitle) || 'page';
};

const ensureCleanDirectory = (directoryPath: string) => {
    fs.mkdirSync(directoryPath, { recursive: true });
    const preservePattern = /^datasheet.*\.json$/i;
    for (const entry of fs.readdirSync(directoryPath)) {
        if (preservePattern.test(entry)) continue;
        fs.rmSync(path.join(directoryPath, entry), { recursive: true, force: true });
    }
};

const toCommentValue = (value: string) => normalizeWhitespace(value || '').replace(/\r?\n/g, ' ');

const buildPageSlugMap = (pages: PageResult[]) => {
    const slugMap = new Map<string, string>();
    const usedSlugs = new Set<string>();

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

const finalizePages = (pages: PageResult[]): FinalizedPageResult[] => {
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

const writePageFormulaFile = (outputDir: string, pageResult: FinalizedPageResult) => {
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

    fs.writeFileSync(path.join(outputDir, pageResult.outputFile), content, 'utf8');
};

const writeSummaryFiles = (outputDir: string, pages: FinalizedPageResult[], options: CrawlOptions) => {
    const allFormulas = pages.flatMap((page) => page.formulas);
    const generatedAt = new Date().toISOString();
    const latexDocument = allFormulas
        .map((formula) =>
            [
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
            ].join('\n'),
        )
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

    fs.writeFileSync(path.join(outputDir, 'dataset.tex'), `${datasetHeader}\n\n${latexDocument}`, 'utf8');
    fs.writeFileSync(path.join(outputDir, 'dataset.json'), JSON.stringify(summary, null, 2), 'utf8');
    fs.writeFileSync(path.join(outputDir, 'dataset.jsonl'), jsonlDocument, 'utf8');
};

const extractNextLinks = (
    $: CheerioAPI,
    currentUrl: string,
    startHost: string,
    scopePathPrefix: string,
    ignoredPathFragments: string[],
) => {
    const containers = [getArticleRoot($), $('main').first(), $('body').first()].filter((node) => node.length > 0);
    const collectedLinks = new Set<string>();

    for (const container of containers) {
        container
            .find('a[href]')
            .map((_, element) => $(element).attr('href'))
            .get()
            .map((href) => (href ? toAbsoluteUrl(href, currentUrl) : null))
            .filter((href): href is string => Boolean(href))
            .filter((href) => isAllowedPage(href, startHost, scopePathPrefix, ignoredPathFragments))
            .forEach((href) => collectedLinks.add(href));
    }

    return [...collectedLinks];
};

const crawlFormulaSheetPage = async (page: Page, url: string): Promise<PageResult | null> => {
    try {
        await page.goto(url, { waitUntil: 'networkidle2' });
        await page.waitForSelector('.resultCont.formula', { timeout: 20_000 });
    } catch {
        console.error('skip', url, 'formulasheet-timeout');
        return null;
    }

    const html = await page.content();
    const $ = load(html);
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


const createBrowser = async (): Promise<Browser> =>
    puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

const createPage = async (browser: Browser): Promise<Page> => {
    const page = await browser.newPage();
    await page.setUserAgent(USER_AGENT);
    await page.setExtraHTTPHeaders({
        'accept-language': 'en-US,en;q=0.9',
    });
    page.setDefaultNavigationTimeout(60_000);
    return page;
};

const crawlPage = async (page: Page, url: string, options: CrawlOptions): Promise<PageResult | null> => {
    let response;
    try {
        response = await page.goto(url, { waitUntil: 'networkidle2' });
    } catch (error) {
        console.error('skip', url, 'navigation-failed');
        return null;
    }

    if (!response || !response.ok()) {
        console.error('skip', url, response?.status() ?? 'no-response');
        return null;
    }

    const html = await page.content();
    const $ = load(html);
    const pageTitle = normalizeWhitespace($('title').first().text()) || url;
    const formulas = extractFormulas($, pageTitle, url);
    const nextLinks = extractNextLinks(
        $,
        url,
        new URL(options.startUrl).host,
        options.scopePathPrefix,
        options.ignoredPathFragments,
    );

    console.log('page', url, 'formulas', formulas.length);

    return {
        title: pageTitle,
        url,
        subjectSlug: getSubjectSlug(url),
        subjectPath: getSubjectPath(url),
        formulas,
        nextLinks,
    };
};

const crawlSite = async (options: CrawlOptions) => {
    ensureCleanDirectory(options.outputDir);

    const browser = await createBrowser();
    const page = await createPage(browser);

    const queue = Array.from(new Set([options.startUrl, ...(options.seedUrls ?? [])].filter(Boolean)));
    const seen = new Set<string>();
    const pages: PageResult[] = [];

    try {
        while (queue.length > 0 && seen.size < options.maxPages) {
            const currentUrl = queue.shift();
            if (!currentUrl || seen.has(currentUrl)) {
                continue;
            }

            seen.add(currentUrl);

            const pageResult = await crawlPage(page, currentUrl, options);
            if (!pageResult) {
                continue;
            }

            pages.push(pageResult);

            for (const nextLink of pageResult.nextLinks) {
                if (seen.has(nextLink) || queue.includes(nextLink)) {
                    continue;
                }
                queue.push(nextLink);
            }
        }
        const formulaSheetPages: PageResult[] = [];
        const formulaSheetUrls = Array.from(new Set(options.formulaSheetUrls ?? []));
        for (const formulaUrl of formulaSheetUrls) {
            const formulaPageTab = await createPage(browser);
            await formulaPageTab.setCacheEnabled(false);
            try {
                const formulaPage = await crawlFormulaSheetPage(formulaPageTab, formulaUrl);
                if (formulaPage) {
                    formulaSheetPages.push(formulaPage);
                }
            } finally {
                await formulaPageTab.close();
            }
        }

        pages.push(...formulaSheetPages);

    } finally {
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

const startUrl = 'https://www.mathsisfun.com/algebra/exponent-laws.html';
const seedUrls: string[] = [
    'https://www.mathsisfun.com/algebra/index.html',
    'https://www.mathsisfun.com/algebra/exponent-laws.html',
    'https://www.mathsisfun.com/algebra/exponents.html',
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
    startUrl,
    seedUrls,
    formulaSheetUrls,
    maxPages: Number(process.env.CRAWL_MAX_PAGES ?? '25'),
    outputDir: process.env.CRAWL_OUTPUT_DIR ?? path.join(process.cwd(), 'formulas'),
    scopePathPrefix: '/',
    ignoredPathFragments: [
        '/wp-',
        '/feed',
        '/tag/',
        '/category/',
        '/privacy-policy',
        '/contact',
        '/about',
        '/blog',
        '/comments',
    ],
});
