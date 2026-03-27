import fs from 'fs';
import path from 'path';

type FormulaRecord = {
    latex: string;
    formulaName?: string;
    section?: string;
    subsection?: string;
    pageTitle?: string;
    pageUrl?: string;
    pageSlug?: string;
    subjectSlug?: string;
    subjectPath?: string;
    source?: string;
    indexInPage?: number;
    indexGlobal?: number;
    formulaId?: string;
    imagePath?: string;
};

type PageSummary = {
    pageSlug: string;
    title: string;
    url: string;
    outputFile: string;
    subjectSlug: string;
    subjectPath: string;
    formulaCount: number;
};

type DatasetFile = {
    dataset?: string;
    generatedAt?: string;
    crawl?: {
        startUrl?: string;
        scopePathPrefix?: string;
        maxPages?: number;
        outputDir?: string;
        totalPages?: number;
        totalFormulas?: number;
    };
    pages?: PageSummary[];
    formulas?: FormulaRecord[];
};

type DataSheetRow = {
    formula: string;
    label: string | null;
    description: string | null;
    latex: string;
};

const toCommentValue = (value: string) => (value || '').replace(/\s+/g, ' ').trim().replace(/\r?\n/g, ' ');

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

const rebuildDatasetTex = (dataset: DatasetFile, formulas: FormulaRecord[]) => {
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
        .map((formula) =>
            [
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
            ].join('\n'),
        )
        .join('\n\n');

    return `${header}\n\n${body}`;
};

const cleanDataset = () => {
    const outputDir = process.env.CLEAN_OUTPUT_DIR ?? path.join(process.cwd(), 'formulas');
    const inputPath = process.env.CLEAN_INPUT ?? path.join(outputDir, 'dataset.json');
    const outputMode = (process.env.CLEAN_OUTPUT_MODE ?? 'overwrite').toLowerCase();
    const suffix = outputMode === 'separate' ? '.clean' : '';

    if (!fs.existsSync(inputPath)) {
        console.error('missing dataset.json', inputPath);
        process.exitCode = 1;
        return;
    }

    const raw = fs.readFileSync(inputPath, 'utf8');
    const dataset = JSON.parse(raw) as DatasetFile;
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

    const countsByPageSlug = new Map<string, number>();
    for (const formula of filtered) {
        const pageSlug = formula.pageSlug ?? '';
        if (!pageSlug) continue;
        countsByPageSlug.set(pageSlug, (countsByPageSlug.get(pageSlug) ?? 0) + 1);
    }

    const pages = (dataset.pages ?? []).map((page) => ({
        ...page,
        formulaCount: countsByPageSlug.get(page.pageSlug) ?? 0,
    }));

    const cleanedDataset: DatasetFile = {
        ...dataset,
        crawl: {
            ...dataset.crawl,
            totalFormulas: filtered.length,
        },
        pages,
        formulas: filtered,
    };

    const outputJson = path.join(outputDir, `dataset${suffix}.json`);
    const outputJsonl = path.join(outputDir, `dataset${suffix}.jsonl`);
    const outputTex = path.join(outputDir, `dataset${suffix}.tex`);
    const outputDatasheet = path.join(outputDir, `datasheet${suffix}.json`);

    fs.writeFileSync(outputJson, JSON.stringify(cleanedDataset, null, 2), 'utf8');
    fs.writeFileSync(outputJsonl, filtered.map((formula) => JSON.stringify(formula)).join('\n'), 'utf8');
    fs.writeFileSync(outputTex, rebuildDatasetTex(cleanedDataset, filtered), 'utf8');
    let existingDatasheet: DataSheetRow[] = [];
    if (fs.existsSync(outputDatasheet)) {
        try {
            const rawDatasheet = fs.readFileSync(outputDatasheet, 'utf8');
            const parsed = JSON.parse(rawDatasheet);
            if (Array.isArray(parsed)) {
                existingDatasheet = parsed.filter(
                    (row): row is DataSheetRow =>
                        typeof row?.formula === 'string' && typeof row?.latex === 'string',
                );
            }
        } catch {
            existingDatasheet = [];
        }
    }

    const existingMap = new Map<string, DataSheetRow>();
    existingDatasheet.forEach((row) => {
        if (!row.formula) return;
        existingMap.set(row.formula, row);
    });

    const newRows: DataSheetRow[] = filtered.map((formula) => {
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

    fs.writeFileSync(outputDatasheet, JSON.stringify(datasheetRows, null, 2), 'utf8');

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
