const fs = require('fs');

let data = JSON.parse(fs.readFileSync('formulas/datasheet.json', 'utf8'));

// Những thứ cần bọc \( ... \)
const wrapRegex = /(?:\\[a-zA-Z]+(?:{[^{}]+})*|[a-zA-Z0-9_]+\^[a-zA-Z0-9_]+|[a-zA-Z0-9_]+_[a-zA-Z0-9_]+|\b[a-zA-Z0-9_]+\/[a-zA-Z0-9_]+\b)/g;

function wrapString(str) {
    if (!str.includes('\\') && !str.includes('^') && !str.includes('_')) {
        return str;
    }
    // Simple heuristic: if it contains \frac or \sqrt or similar, wrap it
    // But we don't want to wrap already wrapped things.
    if (str.includes('\\(') || str.includes('$$') || str.includes('\\[')) {
        return str;
    }

    // Split text by spaces and see if a token is mathy
    let words = str.split(' ');
    for (let i = 0; i < words.length; i++) {
        let w = words[i];
        if (w.includes('\\sqrt') || w.includes('\\frac') || w.includes('\\sin') || w.includes('\\cos') || w.includes('\\tan') || w.includes('\\cot') || w.includes('^') || w.includes('_') || w.includes('\\pmod')) {
            // Remove trailing punctuation
            let prefix = '';
            let suffix = '';
            // If punctuation attached:
            if (w.match(/^[.,:;]/)) {
                prefix = w[0];
                w = w.slice(1);
            }
            if (w.match(/[.,:;)]$/)) {
                suffix = w.slice(-1);
                w = w.slice(0, -1);
            }
            // wrap
            words[i] = `${prefix}\\(${w}\\)${suffix}`;
        }
    }
    return words.join(' ');
}

let modified = 0;
data.forEach(item => {
    if (item.steps) {
        let oldSteps = JSON.stringify(item.steps);
        item.steps = item.steps.map(wrapString);
        if (JSON.stringify(item.steps) !== oldSteps) modified++;
    }
    if (item.reasoning) {
        let oldR = item.reasoning;
        item.reasoning = wrapString(item.reasoning);
        if (item.reasoning !== oldR) modified++;
    }
});

fs.writeFileSync('formulas/datasheet.json', JSON.stringify(data, null, 2));
console.log('Wrapped inline math in', modified, 'items.');
