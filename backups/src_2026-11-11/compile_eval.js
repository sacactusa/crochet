/**
 * compile_eval.js
 *
 * Evaluates normalized DSL translations using the official headless CrochetPARADE compiler.
 * - Format errors (multi-line or prose responses) are recorded directly as invalid (valid = false).
 * - Implements two protocols:
 *   1. Standalone Protocol: Evaluates candidate DSL line in isolation (119 items).
 *   2. Contextual Protocol: Evaluates candidate DSL appended after valid human reference prefix (117 items).
 *      (early_15 and mid_9 excluded per proposal Table 3.3).
 */

const fs = require('fs');
const path = require('path');
const compiler = require('../harness/compiler');

const NORMALIZED_FILE = path.join(__dirname, '..', 'data', 'normalized_records.json');
const PROMPTS_FILE = path.join(__dirname, '..', 'prompts', 'prompts.json');
const RESULTS_FILE = path.join(__dirname, '..', 'results', 'compilation_results.json');
const EXCLUDED_CONTEXTUAL = ['early_15', 'mid_9'];

function runCompilationEvaluation() {
    if (!fs.existsSync(NORMALIZED_FILE)) {
        throw new Error(`Missing ${NORMALIZED_FILE}`);
    }
    if (!fs.existsSync(PROMPTS_FILE)) {
        throw new Error(`Missing ${PROMPTS_FILE}`);
    }

    const records = JSON.parse(fs.readFileSync(NORMALIZED_FILE, 'utf8'));
    const prompts = JSON.parse(fs.readFileSync(PROMPTS_FILE, 'utf8'));

    // Extract reference prefix from prompts
    const prefixes = {};
    for (const [key, val] of Object.entries(prompts)) {
        const pText = val.prompt || '';
        const lines = pText.split('\n');
        const prefixDsl = [];
        let inPrevious = false;
        for (const line of lines) {
            if (line.includes('Previous NL and DSL:')) {
                inPrevious = true;
                continue;
            }
            if (line.startsWith('NL:') && !inPrevious) {
                break;
            }
            if (inPrevious && line.startsWith('DSL:')) {
                const dslPart = line.substring(4).trim();
                if (dslPart) prefixDsl.push(dslPart);
            }
        }
        prefixes[key] = prefixDsl.join('\n');
    }

    const evalResults = [];
    let standaloneValid = 0;
    let contextualValid = 0;
    let contextualTotal = 0;

    for (const r of records) {
        const itemId = r.item_id;
        const candidateDsl = r.normalized_dsl || '';
        const condition = r.condition || r.mode || 'UNKNOWN';
        const source = r.source;
        const formatError = r.format_error === true;
        const formatReason = r.format_error_reason || 'Format error';

        let resStandalone;
        if (formatError) {
            resStandalone = { valid: false, error: formatReason, warningsCount: 0 };
        } else {
            resStandalone = compiler.compile(candidateDsl);
        }
        if (resStandalone.valid) standaloneValid++;

        // Contextual Protocol
        let resContextual = null;
        let isExcludedContextual = EXCLUDED_CONTEXTUAL.includes(itemId);

        if (!isExcludedContextual) {
            contextualTotal++;
            if (formatError) {
                resContextual = { valid: false, error: formatReason, warningsCount: 0 };
            } else {
                const prefix = prefixes[itemId] || '';
                const fullContextCode = prefix ? `${prefix}\n${candidateDsl}` : candidateDsl;
                resContextual = compiler.compile(fullContextCode);
            }
            if (resContextual.valid) contextualValid++;
        }

        evalResults.push({
            request_id: r.request_id || null,
            item_id: itemId,
            condition: condition,
            source: source,
            normalized_dsl: candidateDsl,
            format_error: formatError,
            format_error_reason: formatError ? formatReason : null,
            standalone: {
                valid: resStandalone.valid,
                error: resStandalone.error,
                warningsCount: resStandalone.warningsCount || 0
            },
            contextual: isExcludedContextual ? {
                excluded: true,
                reason: 'Reference prefix contains invalid syntax per Proposal Table 3.3'
            } : {
                valid: resContextual.valid,
                error: resContextual.error,
                warningsCount: resContextual.warningsCount || 0
            }
        });
    }

    fs.mkdirSync(path.dirname(RESULTS_FILE), { recursive: true });
    fs.writeFileSync(RESULTS_FILE, JSON.stringify(evalResults, null, 2), 'utf8');

    console.log(`Evaluated ${evalResults.length} records.`);
    console.log(`Standalone Valid: ${standaloneValid}/${evalResults.length} (${(standaloneValid/evalResults.length*100).toFixed(2)}%)`);
    console.log(`Contextual Valid: ${contextualValid}/${contextualTotal} (${(contextualValid/contextualTotal*100).toFixed(2)}%)`);
    console.log(`Results saved to ${RESULTS_FILE}`);
}

if (require.main === module) {
    runCompilationEvaluation();
}
