/**
 * Rule-Based Translation Execution (R-A0 and R-A1)
 * Using deterministic_translator.js from CrochetPARADE commit be11c8b0a37f2fdeaca39bd2c1cd2b0cc7fc281d
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');
const compiler = require('../harness/compiler.js');

// Load deterministic_translator.js
let translatorSrc = fs.readFileSync('harness/crochetparade/deterministic_translator.js', 'utf8');
translatorSrc = translatorSrc.replace('buildStaticReviewModel,', 'buildStaticReviewModel,\n    buildReviewModel,\n    generateCandidatesForUnit,\n    validateCandidate,\n    candidateNonCommentLines,');
translatorSrc = translatorSrc.replace('const validatorPrefixLines = [];', 'const validatorPrefixLines = (opts.prefixLines || []).slice();');

function createTranslatorInstance() {
    const sandbox = { console, module: { exports: {} }, exports: {} };
    sandbox.globalThis = sandbox;
    sandbox.window = sandbox;
    vm.runInNewContext(translatorSrc, sandbox);
    return sandbox.module.exports;
}

const items = JSON.parse(fs.readFileSync('data/items_standalone.json', 'utf8'));

function createValidator(compilerContext) {
    return function(text) {
        const res = compilerContext.compile(text);
        return { ok: res.valid, error: res.error || '', lastCount: null };
    };
}

function runExecutionPass(passNumber) {
    const translator = createTranslatorInstance();
    const compilerContext = compiler.createCompilerContext();
    const validator = createValidator(compilerContext);
    
    const records = [];
    
    items.forEach((it) => {
        const itemKey = it.item_key;
        const targetNl = it.target_nl;
        const prefixDslBlocks = it.prefix_dsl_blocks || [];
        const timestamp = new Date().toISOString();
        
        // 1. R-A0: No compiler validator
        const m0 = translator.buildReviewModel(targetNl, { validator: null });
        const resp0 = m0.previewCpText;
        records.push({
            pass: passNumber,
            item_id: itemKey,
            id: it.id,
            condition_id: 'R-A0',
            protocol_variant: 'all',
            model_id: 'deterministic_translator.js',
            params_sent: { validator: false, prefix: false },
            prompt_hash: it.prompt_hash,
            target_nl: targetNl,
            raw_response: resp0,
            finish_reason: 'STOP',
            tokens_in: null,
            tokens_out: null,
            tokens_thinking: null,
            error: null,
            timestamp: timestamp
        });
        
        // 2. R-A1 Standalone: Compiler validator without prefix
        const m1_s = translator.buildReviewModel(targetNl, { validator: validator, prefixLines: [] });
        const resp1_s = m1_s.previewCpText;
        records.push({
            pass: passNumber,
            item_id: itemKey,
            id: it.id,
            condition_id: 'R-A1',
            protocol_variant: 'standalone',
            model_id: 'deterministic_translator.js',
            params_sent: { validator: true, prefix: false },
            prompt_hash: it.prompt_hash,
            target_nl: targetNl,
            raw_response: resp1_s,
            finish_reason: 'STOP',
            tokens_in: null,
            tokens_out: null,
            tokens_thinking: null,
            error: null,
            timestamp: timestamp
        });

        // 3. R-A1 Contextual: Compiler validator with reference prefix
        const m1_c = translator.buildReviewModel(targetNl, { validator: validator, prefixLines: prefixDslBlocks });
        const resp1_c = m1_c.previewCpText;
        records.push({
            pass: passNumber,
            item_id: itemKey,
            id: it.id,
            condition_id: 'R-A1',
            protocol_variant: 'contextual',
            model_id: 'deterministic_translator.js',
            params_sent: { validator: true, prefix: true },
            prompt_hash: it.prompt_hash,
            target_nl: targetNl,
            raw_response: resp1_c,
            finish_reason: 'STOP',
            tokens_in: null,
            tokens_out: null,
            tokens_thinking: null,
            error: null,
            timestamp: timestamp
        });
    });
    
    return records;
}

console.log('Running Pass 1 of Rule-Based execution...');
const pass1 = runExecutionPass(1);
console.log(`Pass 1 completed. Total records: ${pass1.length}`);

console.log('Running Pass 2 of Rule-Based execution...');
const pass2 = runExecutionPass(2);
console.log(`Pass 2 completed. Total records: ${pass2.length}`);

// Compare outputs between Pass 1 and Pass 2 (ignoring timestamp and pass number)
function hashRecords(records) {
    const comparable = records.map(r => ({
        item_id: r.item_id,
        id: r.id,
        condition_id: r.condition_id,
        protocol_variant: r.protocol_variant,
        raw_response: r.raw_response
    }));
    const jsonStr = JSON.stringify(comparable);
    return crypto.createHash('sha256').update(jsonStr).digest('hex');
}

const hash1 = hashRecords(pass1);
const hash2 = hashRecords(pass2);

console.log('\n--- Determinism Verification ---');
console.log(`Pass 1 Output SHA-256 Hash: ${hash1}`);
console.log(`Pass 2 Output SHA-256 Hash: ${hash2}`);
console.log(`Hashes Identical: ${hash1 === hash2}`);

if (hash1 !== hash2) {
    console.error('FATAL: Rule-based outputs are NOT deterministic!');
    process.exit(1);
}

// Save to raw/rule_based.jsonl
os = require('os');
const outLines = pass1.map(r => {
    // Clean record for output
    const outRecord = { ...r };
    delete outRecord.pass;
    return JSON.stringify(outRecord);
});

fs.mkdirSync('raw', { recursive: true });
fs.writeFileSync('raw/rule_based.jsonl', outLines.join('\n') + '\n', 'utf8');
console.log(`\nSuccessfully saved ${outLines.length} records to raw/rule_based.jsonl`);

