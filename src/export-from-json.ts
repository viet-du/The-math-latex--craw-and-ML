import fs from 'fs';
import path from 'path';
import puppeteer from 'puppeteer';

type FormulaRecord = {
    latex: string;
    formulaName?: string;
    label?: string | null;
    description?: string | null;
    section?: string;
    subsection?: string;
    pageTitle?: string;
    pageUrl?: string;
    formulaId?: string;
};

type DatasetFile = {
    dataset?: string;
    generatedAt?: string;
    formulas?: FormulaRecord[];
};

type DataSheetRow = {
    formula?: string;
    latex?: string;
    label?: string | null;
    description?: string | null;
};

const escapeHtml = (value: string) =>
    value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');

const readJsonFile = <T>(filePath: string): T => {
    const raw = fs.readFileSync(filePath, 'utf8');
    const cleaned = raw.replace(/^\uFEFF/, '').trimStart();
    return JSON.parse(cleaned) as T;
};

const normalizeLabel = (value?: string | null) => (value ?? '').trim();

const hasUnbalancedEnvironment = (latex: string) => {
    const beginMatches = [...latex.matchAll(/\\begin\{([^}]+)\}/g)];
    const endMatches = [...latex.matchAll(/\\end\{([^}]+)\}/g)];
    if (beginMatches.length === 0 && endMatches.length === 0) return false;

    const counts = new Map<string, number>();
    for (const match of beginMatches) {
        const name = match[1] ?? '';
        counts.set(name, (counts.get(name) ?? 0) + 1);
    }
    for (const match of endMatches) {
        const name = match[1] ?? '';
        counts.set(name, (counts.get(name) ?? 0) - 1);
    }
    for (const count of counts.values()) {
        if (count !== 0) return true;
    }
    return false;
};

const shouldSkipFormula = (formula: FormulaRecord) => {
    const latex = (formula.latex ?? '').trim();
    if (!latex) return true;
    if (hasUnbalancedEnvironment(latex)) return true;
    return false;
};

const buildHtml = (dataset: DatasetFile, formulas: FormulaRecord[]) => {
    const datasetName = escapeHtml(dataset.dataset ?? 'math-formula-atlas');
    const generatedAt = escapeHtml(dataset.generatedAt ?? '');
    const formulaBlocks = formulas
        .map((formula, index) => {
            const label = normalizeLabel(formula.label ?? formula.formulaName);
            const description = normalizeLabel(formula.description);
            const latex = escapeHtml(formula.latex);
            const section = escapeHtml(formula.section ?? '');
            const subsection = escapeHtml(formula.subsection ?? '');
            const pageTitle = escapeHtml(formula.pageTitle ?? '');
            const pageUrl = escapeHtml(formula.pageUrl ?? '');
            const formulaId = escapeHtml(formula.formulaId ?? `formula-${index + 1}`);

            return `
            <article class="formula-card">
                ${label ? `<div class="label">Label: ${escapeHtml(label)}</div>` : ''}
                ${description ? `<div class="description">Description: ${escapeHtml(description)}</div>` : ''}
                <div class="math">\\[${latex}\\]</div>
                <div class="meta">
                    <span class="meta-item">ID: ${formulaId}</span>
                    ${section ? `<span class="meta-item">Section: ${section}</span>` : ''}
                    ${subsection ? `<span class="meta-item">Subsection: ${subsection}</span>` : ''}
                    ${pageTitle ? `<span class="meta-item">Page: ${pageTitle}</span>` : ''}
                    ${pageUrl ? `<span class="meta-item">URL: ${pageUrl}</span>` : ''}
                </div>
            </article>
            `;
        })
        .join('\n');

    return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Formula Preview</title>
    <style>
      :root {
        color-scheme: light;
      }
      body {
        font-family: "Times New Roman", Georgia, serif;
        color: #111;
        background: #fff;
        margin: 24px;
      }
      header {
        margin-bottom: 24px;
      }
      h1 {
        font-size: 22px;
        margin: 0 0 6px;
      }
      .subtitle {
        font-size: 13px;
        color: #555;
      }
      .formula-card {
        padding: 12px 0 16px;
        border-bottom: 1px solid #e6e6e6;
      }
      .label {
        font-weight: 700;
        margin-bottom: 6px;
      }
      .description {
        font-size: 12px;
        color: #444;
        margin-bottom: 6px;
      }
      .math {
        font-size: 18px;
        margin: 4px 0 6px;
      }
      .meta {
        font-size: 12px;
        color: #666;
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }
      .meta-item {
        white-space: nowrap;
      }
    </style>
    <script>
      window.MathJax = {
        tex: {
          inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
          displayMath: [['\\\\[', '\\\\]']],
        },
        options: {
          skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
        }
      };
    </script>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" async></script>
  </head>
  <body>
    <header>
      <h1>Formula Preview</h1>
      <div class="subtitle">Dataset: ${datasetName}${generatedAt ? ` · Generated: ${generatedAt}` : ''}</div>
    </header>
    ${formulaBlocks}
  </body>
</html>`;
};

const exportFromJson = async () => {
    const outputDir = process.env.EXPORT_OUTPUT_DIR ?? path.join(process.cwd(), 'formulas');
    const inputPath = process.env.EXPORT_INPUT ?? path.join(outputDir, 'dataset.json');
    const datasheetPath = process.env.EXPORT_DATASHEET ?? path.join(outputDir, 'datasheet.json');
    const useDatasheet = (process.env.EXPORT_USE_DATASHEET ?? '1') !== '0';
    const outputHtml = process.env.EXPORT_HTML ?? path.join(outputDir, 'preview.html');
    const outputPdf = process.env.EXPORT_PDF ?? path.join(outputDir, 'preview.pdf');
    const enablePdf = (process.env.EXPORT_PDF_ENABLED ?? '1') !== '0';

    let dataset: DatasetFile = { dataset: 'math-formula-atlas', generatedAt: '' };
    let formulas: FormulaRecord[] = [];

    if (useDatasheet && fs.existsSync(datasheetPath)) {
        const rows = readJsonFile<DataSheetRow[]>(datasheetPath);
        if (!Array.isArray(rows)) {
            console.error('datasheet.json is not an array', datasheetPath);
            process.exitCode = 1;
            return;
        }
        dataset = { dataset: 'datasheet', generatedAt: '' };
        formulas = rows
            .map((row) => {
                const latex = (row.latex ?? row.formula ?? '').trim();
                if (!latex) return null;
                return {
                    latex,
                    label: row.label ?? null,
                    description: row.description ?? null,
                } as FormulaRecord;
            })
            .filter((row): row is FormulaRecord => Boolean(row));
    } else {
        if (!fs.existsSync(inputPath)) {
            console.error('missing dataset.json', inputPath);
            process.exitCode = 1;
            return;
        }
        dataset = readJsonFile<DatasetFile>(inputPath);
        formulas = Array.isArray(dataset.formulas) ? dataset.formulas : [];
    }
    const filteredFormulas = formulas.filter((formula) => !shouldSkipFormula(formula));

    if (formulas.length === 0) {
        console.error('no formulas to export', useDatasheet && fs.existsSync(datasheetPath) ? datasheetPath : inputPath);
        process.exitCode = 1;
        return;
    }

    if (filteredFormulas.length === 0) {
        console.error('all formulas were filtered out due to invalid latex', inputPath);
        process.exitCode = 1;
        return;
    }

    fs.mkdirSync(outputDir, { recursive: true });
    const html = buildHtml(dataset, filteredFormulas);
    fs.writeFileSync(outputHtml, html, 'utf8');
    console.log('preview html', outputHtml, 'formulas', filteredFormulas.length, 'skipped', formulas.length - filteredFormulas.length);

    if (!enablePdf) return;

    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    const setContentTimeout = Number(process.env.EXPORT_SETCONTENT_TIMEOUT ?? '10000');
    await page.setContent(html, { waitUntil: 'domcontentloaded', timeout: setContentTimeout });

    try {
        await page.waitForFunction('window.MathJax && window.MathJax.typesetPromise', { timeout: 15000 });
        await page.evaluate(() => {
            const mathjax = (window as unknown as { MathJax?: { typesetPromise?: () => Promise<void> } }).MathJax;
            if (mathjax?.typesetPromise) {
                return mathjax.typesetPromise();
            }
            return null;
        });
    } catch {
        console.warn('mathjax not ready, exporting pdf without waiting');
    }

    await page.pdf({
        path: outputPdf,
        format: 'A4',
        printBackground: true,
        margin: { top: '16mm', bottom: '16mm', left: '14mm', right: '14mm' },
    });
    await browser.close();

    console.log('preview pdf', outputPdf);
};

void exportFromJson();
