"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const escapeCsv = (value) => {
    const normalized = value.replace(/\r?\n/g, ' ').trim();
    if (/[",\n]/.test(normalized)) {
        return `"${normalized.replace(/"/g, '""')}"`;
    }
    return normalized;
};
const exportLabeling = () => {
    const inputPath = process.env.LABEL_INPUT ?? path_1.default.join(process.cwd(), 'formulas', 'dataset.json');
    const outputDir = process.env.LABEL_OUTPUT_DIR ?? path_1.default.join(process.cwd(), 'formulas');
    const outputCsv = process.env.LABEL_OUTPUT ?? path_1.default.join(outputDir, 'labeling.csv');
    const outputJsonl = process.env.LABEL_OUTPUT_JSONL ?? path_1.default.join(outputDir, 'labeling.jsonl');
    const limit = Number(process.env.LABEL_LIMIT ?? '0');
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
    const selected = limit > 0 ? formulas.slice(0, limit) : formulas;
    fs_1.default.mkdirSync(outputDir, { recursive: true });
    const header = [
        'formulaId',
        'latex',
        'section',
        'subsection',
        'pageTitle',
        'pageUrl',
        'source',
        'label',
    ];
    const rows = selected.map((formula) => [
        formula.formulaId ?? '',
        formula.latex ?? '',
        formula.section ?? '',
        formula.subsection ?? '',
        formula.pageTitle ?? '',
        formula.pageUrl ?? '',
        formula.source ?? '',
        formula.formulaName ?? '',
    ]);
    const csv = [header, ...rows].map((row) => row.map(escapeCsv).join(',')).join('\n');
    fs_1.default.writeFileSync(outputCsv, csv, 'utf8');
    const jsonl = selected
        .map((formula) => JSON.stringify({
        formulaId: formula.formulaId ?? '',
        latex: formula.latex ?? '',
        section: formula.section ?? '',
        subsection: formula.subsection ?? '',
        pageTitle: formula.pageTitle ?? '',
        pageUrl: formula.pageUrl ?? '',
        source: formula.source ?? '',
        label: formula.formulaName ?? '',
    }))
        .join('\n');
    fs_1.default.writeFileSync(outputJsonl, jsonl, 'utf8');
    console.log('labeling export', {
        input: inputPath,
        outputCsv,
        outputJsonl,
        total: selected.length,
    });
};
exportLabeling();
