"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const puppeteer_1 = __importDefault(require("puppeteer"));
// ============================================================
// HELPERS
// ============================================================
const escapeHtml = (value) => value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
const readJsonFile = (filePath) => {
    const raw = fs_1.default.readFileSync(filePath, 'utf8');
    const cleaned = raw.replace(/^\uFEFF/, '').trimStart();
    return JSON.parse(cleaned);
};
const hasUnbalancedEnvironment = (latex) => {
    const beginMatches = [...latex.matchAll(/\\begin\{([^}]+)\}/g)];
    const endMatches = [...latex.matchAll(/\\end\{([^}]+)\}/g)];
    if (beginMatches.length === 0 && endMatches.length === 0)
        return false;
    const counts = new Map();
    for (const match of beginMatches) {
        const name = match[1] ?? '';
        counts.set(name, (counts.get(name) ?? 0) + 1);
    }
    for (const match of endMatches) {
        const name = match[1] ?? '';
        counts.set(name, (counts.get(name) ?? 0) - 1);
    }
    for (const count of counts.values()) {
        if (count !== 0)
            return true;
    }
    return false;
};
// Bọc LaTeX thô vào \[ ... \] nếu chưa có
const wrapLatex = (latex) => {
    const trimmed = latex.trim();
    if (trimmed.startsWith('\\[') || trimmed.startsWith('\\(') || trimmed.startsWith('$')) {
        return trimmed;
    }
    return `\\[${trimmed}\\]`;
};
const difficultyColor = {
    easy: '#22c55e',
    medium: '#f59e0b',
    hard: '#ef4444',
};
const typeColor = {
    calculus: '#6366f1',
    algebra: '#3b82f6',
    trigonometry: '#8b5cf6',
    geometry: '#10b981',
    statistics: '#f97316',
    optimization: '#ec4899',
    linear_algebra: '#0ea5e9',
    mathematical_physics: '#d946ef',
};
// ============================================================
// BUILD HTML từ DataSheetEntry[]
// ============================================================
const buildHtmlFromDatasheet = (entries) => {
    const cards = entries
        .map((entry, idx) => {
        const outputLatex = escapeHtml(entry.output ?? '');
        const inputLatex = entry.input ? escapeHtml(entry.input) : '';
        const normalizedLatex = entry.output_normalized && entry.output_normalized !== entry.output
            ? escapeHtml(entry.output_normalized)
            : null;
        const diffColor = difficultyColor[entry.difficulty] ?? '#94a3b8';
        const typeCol = typeColor[entry.type] ?? '#64748b';
        const tagBadges = (entry.tags ?? [])
            .map(t => `<span class="tag">${escapeHtml(t)}</span>`)
            .join('');
        const stepsList = (entry.steps ?? [])
            .map((s, i) => `<li><span class="step-num">${i + 1}.</span> ${escapeHtml(s)}</li>`)
            .join('');
        const constraintsList = (entry.constraints ?? [])
            .map(c => `<li>\\(${escapeHtml(c)}\\)</li>`)
            .join('');
        const negList = (entry.negative_examples ?? [])
            .map(n => `<li class="neg">\\(${escapeHtml(n)}\\)</li>`)
            .join('');
        return `
<article class="card" id="card-${idx + 1}">
  <div class="card-header">
    <div class="card-id">#${escapeHtml(entry.id)}</div>
    <div class="badges">
      <span class="badge" style="background:${typeCol}">${escapeHtml(entry.type)}</span>
      <span class="badge" style="background:${diffColor}">${escapeHtml(entry.difficulty)}</span>
    </div>
  </div>

  <div class="instruction">${escapeHtml(entry.instruction)}</div>

  ${inputLatex ? `
  <div class="field-label">Input</div>
  <div class="math-block">\\[${inputLatex}\\]</div>
  ` : ''}

  <div class="field-label">Output</div>
  <div class="math-block">\\[${outputLatex}\\]</div>

  ${normalizedLatex ? `
  <div class="field-label">Output (SymPy normalized)</div>
  <div class="math-block normalized">\\[${normalizedLatex}\\]</div>
  ` : ''}

  ${stepsList ? `
  <div class="field-label">Steps</div>
  <ol class="steps-list">${stepsList}</ol>
  ` : ''}

  ${entry.reasoning ? `
  <div class="field-label">Reasoning</div>
  <div class="reasoning">${escapeHtml(entry.reasoning)}</div>
  ` : ''}

  ${constraintsList ? `
  <div class="field-label">Constraints</div>
  <ul class="constraints-list">${constraintsList}</ul>
  ` : ''}

  ${negList ? `
  <div class="field-label neg-label">Common Mistakes</div>
  <ul class="neg-list">${negList}</ul>
  ` : ''}

  ${tagBadges ? `<div class="tags">${tagBadges}</div>` : ''}
</article>`;
    })
        .join('\n');
    return `<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Math Formula Datasheet</title>
  <style>
    :root { color-scheme: light; }
    * { box-sizing: border-box; }
    body {
      font-family: "Times New Roman", Georgia, serif;
      font-size: 13px;
      color: #111;
      background: #fff;
      margin: 0;
      padding: 20px 24px;
    }
    header {
      border-bottom: 2px solid #1e293b;
      margin-bottom: 20px;
      padding-bottom: 12px;
    }
    header h1 {
      font-size: 20px;
      margin: 0 0 4px;
      color: #1e293b;
    }
    header .subtitle {
      font-size: 11px;
      color: #64748b;
    }

    /* ── Card ── */
    .card {
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 14px 16px;
      margin-bottom: 16px;
      page-break-inside: avoid;
      break-inside: avoid;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 8px;
    }
    .card-id {
      font-size: 10px;
      color: #94a3b8;
      font-family: monospace;
      word-break: break-all;
      flex: 1;
    }
    .badges {
      display: flex;
      gap: 4px;
      flex-shrink: 0;
      margin-left: 8px;
    }
    .badge {
      color: #fff;
      font-size: 9px;
      padding: 2px 6px;
      border-radius: 3px;
      font-family: sans-serif;
      font-weight: 600;
      letter-spacing: 0.4px;
      text-transform: uppercase;
    }

    .instruction {
      font-size: 13px;
      font-weight: 700;
      color: #1e293b;
      margin-bottom: 8px;
    }

    .field-label {
      font-size: 10px;
      font-weight: 700;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      margin: 8px 0 3px;
      font-family: sans-serif;
    }
    .neg-label { color: #dc2626; }

    .math-block {
      font-size: 15px;
      padding: 6px 10px;
      background: #f8fafc;
      border-left: 3px solid #6366f1;
      border-radius: 3px;
      overflow-x: auto;
    }
    .math-block.normalized {
      border-left-color: #22c55e;
      background: #f0fdf4;
    }

    .steps-list {
      margin: 0;
      padding-left: 18px;
      line-height: 1.7;
    }
    .steps-list li { margin-bottom: 2px; }
    .step-num { font-weight: 700; color: #6366f1; }

    .reasoning {
      font-size: 12px;
      color: #475569;
      line-height: 1.6;
      background: #fffbeb;
      border-left: 3px solid #f59e0b;
      padding: 6px 10px;
      border-radius: 3px;
    }

    .constraints-list {
      margin: 0;
      padding-left: 18px;
      font-size: 12px;
      line-height: 1.7;
      color: #374151;
    }

    .neg-list {
      margin: 0;
      padding-left: 18px;
      font-size: 11px;
      line-height: 1.7;
      color: #dc2626;
    }
    .neg { color: #dc2626; }

    .tags {
      margin-top: 8px;
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }
    .tag {
      font-size: 9px;
      padding: 1px 5px;
      border-radius: 2px;
      background: #e2e8f0;
      color: #475569;
      font-family: monospace;
    }
  </style>
  <script>
    window.MathJax = {
      tex: {
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['\\\\[', '\\\\]']],
        tags: 'none'
      },
      options: {
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
      },
      startup: { typeset: true }
    };
  </script>
  <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" async></script>
</head>
<body>
  <header>
    <h1>Math Formula Datasheet</h1>
    <div class="subtitle">
      Total: ${entries.length} entries &nbsp;·&nbsp;
      Generated: ${new Date().toISOString().replace('T', ' ').slice(0, 19)} UTC
    </div>
  </header>
  ${cards}
</body>
</html>`;
};
// ============================================================
// LEGACY HTML builder (dataset.json cũ)
// ============================================================
const buildHtmlLegacy = (dataset, formulas) => {
    const datasetName = escapeHtml(dataset.dataset ?? 'math-formula-atlas');
    const generatedAt = escapeHtml(dataset.generatedAt ?? '');
    const formulaBlocks = formulas
        .map((formula, index) => {
        const label = (formula.label ?? formula.formulaName ?? '').trim();
        const description = (formula.description ?? '').trim();
        const latex = escapeHtml(formula.latex);
        const section = escapeHtml(formula.section ?? '');
        const pageTitle = escapeHtml(formula.pageTitle ?? '');
        const formulaId = escapeHtml(formula.formulaId ?? `formula-${index + 1}`);
        return `
<article class="formula-card">
  ${label ? `<div class="label">Label: ${escapeHtml(label)}</div>` : ''}
  ${description ? `<div class="description">Description: ${escapeHtml(description)}</div>` : ''}
  <div class="math">\\[${latex}\\]</div>
  <div class="meta">
    <span class="meta-item">ID: ${formulaId}</span>
    ${section ? `<span class="meta-item">Section: ${section}</span>` : ''}
    ${pageTitle ? `<span class="meta-item">Page: ${pageTitle}</span>` : ''}
  </div>
</article>`;
    })
        .join('\n');
    return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Formula Preview</title>
  <style>
    body { font-family: "Times New Roman", Georgia, serif; color: #111; background: #fff; margin: 24px; }
    h1 { font-size: 22px; }
    .formula-card { padding: 12px 0 16px; border-bottom: 1px solid #e6e6e6; }
    .label { font-weight: 700; margin-bottom: 6px; }
    .description { font-size: 12px; color: #444; margin-bottom: 6px; }
    .math { font-size: 18px; margin: 4px 0 6px; }
    .meta { font-size: 12px; color: #666; display: flex; flex-wrap: wrap; gap: 10px; }
  </style>
  <script>
    window.MathJax = {
      tex: { inlineMath: [['$','$'],['\\\\(','\\\\)']], displayMath: [['\\\\[','\\\\]']] },
      options: { skipHtmlTags: ['script','noscript','style','textarea','pre','code'] }
    };
  </script>
  <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" async></script>
</head>
<body>
  <header><h1>Formula Preview</h1>
  <div style="font-size:13px;color:#555">Dataset: ${datasetName}${generatedAt ? ` · Generated: ${generatedAt}` : ''}</div>
  </header>
  ${formulaBlocks}
</body>
</html>`;
};
// ============================================================
// MAIN
// ============================================================
const exportFromJson = async () => {
    const outputDir = process.env.EXPORT_OUTPUT_DIR ?? path_1.default.join(process.cwd(), 'formulas');
    const inputPath = process.env.EXPORT_INPUT ?? path_1.default.join(outputDir, 'dataset.json');
    const datasheetPath = process.env.EXPORT_DATASHEET ?? path_1.default.join(outputDir, 'datasheet.json');
    const useDatasheet = (process.env.EXPORT_USE_DATASHEET ?? '1') !== '0';
    const outputHtml = process.env.EXPORT_HTML ?? path_1.default.join(outputDir, 'preview.html');
    const outputPdf = process.env.EXPORT_PDF ?? path_1.default.join(outputDir, 'preview.pdf');
    const enablePdf = (process.env.EXPORT_PDF_ENABLED ?? '1') !== '0';
    const maxEntries = Number(process.env.EXPORT_MAX ?? '0'); // 0 = all
    let html = '';
    let totalEntries = 0;
    let skipped = 0;
    // ── Đọc datasheet.json (schema mới) ──
    if (useDatasheet && fs_1.default.existsSync(datasheetPath)) {
        const raw = readJsonFile(datasheetPath);
        if (!Array.isArray(raw)) {
            console.error('datasheet.json is not an array:', datasheetPath);
            process.exitCode = 1;
            return;
        }
        // Phân loại schema mới vs cũ theo key đặc trưng
        const isNewSchema = raw.length > 0 && 'id' in raw[0] && 'instruction' in raw[0];
        if (isNewSchema) {
            let entries = raw;
            // Lọc bỏ entries thiếu output hoặc bị invalid LaTeX
            const filtered = entries.filter(e => {
                const latex = (e.output ?? '').trim();
                if (!latex) {
                    skipped++;
                    return false;
                }
                if (hasUnbalancedEnvironment(latex)) {
                    skipped++;
                    return false;
                }
                return true;
            });
            if (maxEntries > 0) {
                entries = filtered.slice(0, maxEntries);
            }
            else {
                entries = filtered;
            }
            totalEntries = entries.length;
            if (totalEntries === 0) {
                console.error('No valid entries found in datasheet.json');
                process.exitCode = 1;
                return;
            }
            html = buildHtmlFromDatasheet(entries);
            console.log(`[datasheet] schema=NEW  total=${totalEntries}  skipped=${skipped}`);
        }
        else {
            const rows = raw;
            const formulas = rows
                .map(row => {
                const latex = (row.latex ?? row.formula ?? '').trim();
                if (!latex) {
                    skipped++;
                    return null;
                }
                return { latex, label: row.label ?? null, description: row.description ?? null };
            })
                .filter((r) => Boolean(r));
            const filtered = formulas.filter(f => {
                if (hasUnbalancedEnvironment(f.latex)) {
                    skipped++;
                    return false;
                }
                return true;
            });
            totalEntries = filtered.length;
            html = buildHtmlLegacy({ dataset: 'datasheet', generatedAt: '' }, maxEntries > 0 ? filtered.slice(0, maxEntries) : filtered);
            console.log(`[datasheet] schema=LEGACY  total=${totalEntries}  skipped=${skipped}`);
        }
    }
    else {
        // Fallback: dataset.json gốc
        if (!fs_1.default.existsSync(inputPath)) {
            console.error('Missing dataset.json:', inputPath);
            process.exitCode = 1;
            return;
        }
        const dataset = readJsonFile(inputPath);
        const formulas = Array.isArray(dataset.formulas) ? dataset.formulas : [];
        const filtered = formulas.filter(f => {
            if (!f.latex.trim()) {
                skipped++;
                return false;
            }
            if (hasUnbalancedEnvironment(f.latex)) {
                skipped++;
                return false;
            }
            return true;
        });
        totalEntries = filtered.length;
        html = buildHtmlLegacy(dataset, maxEntries > 0 ? filtered.slice(0, maxEntries) : filtered);
        console.log(`[dataset.json]  total=${totalEntries}  skipped=${skipped}`);
    }
    // ── Ghi HTML ──
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    fs_1.default.writeFileSync(outputHtml, html, 'utf8');
    console.log('HTML saved:', outputHtml);
    if (!enablePdf)
        return;
    // ── Xuất PDF via Puppeteer ──
    const browser = await puppeteer_1.default.launch({ headless: true, protocolTimeout: 0 });
    const page = await browser.newPage();
    const setContentTimeout = Number(process.env.EXPORT_SETCONTENT_TIMEOUT ?? '0');
    await page.setContent(html, { waitUntil: 'domcontentloaded', timeout: setContentTimeout });
    // Chờ MathJax render xong
    try {
        await page.waitForFunction('window.MathJax && window.MathJax.typesetPromise', { timeout: 0 });
        await page.evaluate(() => {
            const mj = window.MathJax;
            return mj?.typesetPromise?.() ?? null;
        });
        // Chờ thêm 5s để render hoàn tất vì file HTML rất lớn
        await new Promise(r => setTimeout(r, 5000));
    }
    catch {
        console.warn('MathJax not ready, exporting PDF without waiting for typeset');
    }
    await page.pdf({
        path: outputPdf,
        format: 'A4',
        printBackground: true,
        timeout: 0,
        margin: { top: '16mm', bottom: '16mm', left: '14mm', right: '14mm' },
    });
    await browser.close();
    console.log('PDF saved:', outputPdf);
};
void exportFromJson();
