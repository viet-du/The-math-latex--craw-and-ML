"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const toCommentValue = (value) => (value || '').replace(/\s+/g, ' ').trim().replace(/\r?\n/g, ' ');
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
const shouldSkipFormula = (formula) => {
    const latex = (formula.latex ?? '').trim();
    if (!latex)
        return true;
    if (hasUnbalancedEnvironment(latex))
        return true;
    return false;
};
const rebuildDatasetTex = (dataset, formulas) => {
    const generatedAt = dataset.generatedAt ?? new Date().toISOString();
    const header = [
        `% dataset: ${dataset.dataset ?? 'math-formula-atlas'}`,
        `% generated_at: ${generatedAt}`,
        `% start_url: ${dataset.crawl?.startUrl ?? ''}`,
        `% scope_path_prefix: ${dataset.crawl?.scopePathPrefix ?? ''}`,
        `% total_pages: ${dataset.pages?.length ?? 0}`,
        `% total_formulas: ${formulas.length}`,
    ].join('\n');
    const body = formulas
        .map((formula) => [
        `% formula_record_start`,
        `% formula_id: ${formula.formulaId ?? ''}`,
        `% page_slug: ${formula.pageSlug ?? ''}`,
        `% page_title: ${toCommentValue(formula.pageTitle ?? '')}`,
        `% page_url: ${formula.pageUrl ?? ''}`,
        `% subject_slug: ${formula.subjectSlug ?? ''}`,
        `% subject_path: ${formula.subjectPath ?? ''}`,
        `% section: ${toCommentValue(formula.section ?? '')}`,
        `% subsection: ${toCommentValue(formula.subsection ?? '')}`,
        `% formula_name: ${toCommentValue(formula.formulaName ?? '')}`,
        `% source: ${formula.source ?? ''}`,
        `% index_global: ${formula.indexGlobal ?? ''}`,
        `% index_in_page: ${formula.indexInPage ?? ''}`,
        ...(formula.formulaName ? [`\\textbf{Label: ${toCommentValue(formula.formulaName)}}`] : []),
        `\\[${formula.latex}\\]`,
        `% formula_record_end`,
    ].join('\n'))
        .join('\n\n');
    return `${header}\n\n${body}`;
};
const cleanDataset = () => {
    const outputDir = process.env.CLEAN_OUTPUT_DIR ?? path_1.default.join(process.cwd(), 'formulas');
    const inputPath = process.env.CLEAN_INPUT ?? path_1.default.join(outputDir, 'dataset.json');
    const outputMode = (process.env.CLEAN_OUTPUT_MODE ?? 'overwrite').toLowerCase();
    const suffix = outputMode === 'separate' ? '.clean' : '';
    if (!fs_1.default.existsSync(inputPath)) {
        console.error('missing dataset.json', inputPath);
        process.exitCode = 1;
        return;
    }
    const raw = fs_1.default.readFileSync(inputPath, 'utf8');
    const dataset = JSON.parse(raw);
    const formulas = Array.isArray(dataset.formulas) ? dataset.formulas : [];
    if (formulas.length === 0) {
        console.error('dataset.json has no formulas', inputPath);
        process.exitCode = 1;
        return;
    }
    const filtered = formulas.filter((formula) => !shouldSkipFormula(formula));
    const skipped = formulas.length - filtered.length;
    if (filtered.length === 0) {
        console.error('all formulas were filtered out due to invalid latex', inputPath);
        process.exitCode = 1;
        return;
    }
    const countsByPageSlug = new Map();
    for (const formula of filtered) {
        const pageSlug = formula.pageSlug ?? '';
        if (!pageSlug)
            continue;
        countsByPageSlug.set(pageSlug, (countsByPageSlug.get(pageSlug) ?? 0) + 1);
    }
    const pages = (dataset.pages ?? []).map((page) => ({
        ...page,
        formulaCount: countsByPageSlug.get(page.pageSlug) ?? 0,
    }));
    const cleanedDataset = {
        ...dataset,
        crawl: {
            ...dataset.crawl,
            totalFormulas: filtered.length,
        },
        pages,
        formulas: filtered,
    };
    const outputJson = path_1.default.join(outputDir, `dataset${suffix}.json`);
    const outputJsonl = path_1.default.join(outputDir, `dataset${suffix}.jsonl`);
    const outputTex = path_1.default.join(outputDir, `dataset${suffix}.tex`);
    const outputDatasheet = path_1.default.join(outputDir, `datasheet${suffix}.json`);
    fs_1.default.writeFileSync(outputJson, JSON.stringify(cleanedDataset, null, 2), 'utf8');
    fs_1.default.writeFileSync(outputJsonl, filtered.map((formula) => JSON.stringify(formula)).join('\n'), 'utf8');
    fs_1.default.writeFileSync(outputTex, rebuildDatasetTex(cleanedDataset, filtered), 'utf8');
    let existingDatasheet = [];
    if (fs_1.default.existsSync(outputDatasheet)) {
        try {
            const rawDatasheet = fs_1.default.readFileSync(outputDatasheet, 'utf8');
            const parsed = JSON.parse(rawDatasheet);
            if (Array.isArray(parsed)) {
                existingDatasheet = parsed.filter((row) => typeof row?.formula === 'string' && typeof row?.latex === 'string');
            }
        }
        catch {
            existingDatasheet = [];
        }
    }
    const existingMap = new Map();
    existingDatasheet.forEach((row) => {
        if (!row.formula)
            return;
        existingMap.set(row.formula, row);
    });
    const newRows = filtered.map((formula) => {
        const existing = existingMap.get(formula.latex);
        return {
            formula: formula.latex,
            label: existing?.label ?? null,
            description: existing?.description ?? null,
            latex: formula.latex,
        };
    });
    const newFormulaSet = new Set(newRows.map((row) => row.formula));
    const orphanRows = existingDatasheet.filter((row) => !newFormulaSet.has(row.formula));
    const datasheetRows = [...newRows, ...orphanRows];
    fs_1.default.writeFileSync(outputDatasheet, JSON.stringify(datasheetRows, null, 2), 'utf8');
    console.log('cleaned dataset', {
        input: inputPath,
        outputJson,
        outputJsonl,
        outputTex,
        outputDatasheet,
        totalFormulas: filtered.length,
        skipped,
    });
};
cleanDataset();
