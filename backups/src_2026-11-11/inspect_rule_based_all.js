const fs = require('fs');
const vm = require('vm');
const compiler = require('../harness/compiler.js');

let src = fs.readFileSync('harness/crochetparade/deterministic_translator.js', 'utf8');
src = src.replace('buildStaticReviewModel,', 'buildStaticReviewModel,\n    buildReviewModel,\n    generateCandidatesForUnit,\n    validateCandidate,\n    candidateNonCommentLines,');
src = src.replace('const validatorPrefixLines = [];', 'const validatorPrefixLines = (opts.prefixLines || []).slice();');

const sandbox = { console, module: { exports: {} }, exports: {} };
sandbox.globalThis = sandbox;
sandbox.window = sandbox;
vm.runInNewContext(src, sandbox);
const translator = sandbox.module.exports;

const items = JSON.parse(fs.readFileSync('data/items_standalone.json', 'utf8'));

function validator(text) {
    const res = compiler.compile(text);
    return { ok: res.valid, error: res.error || '', lastCount: null };
}

console.log('Testing 119 items on R-A0, R-A1 Standalone, R-A1 Contextual...');

let a0_has_instruction = 0;
let a0_comment_only = 0;
let diff_a0_a1_count = 0;

items.forEach((it, idx) => {
    const nl = it.target_nl;
    
    // R-A0: validator = null
    const m0 = translator.buildReviewModel(nl, { validator: null });
    const cp0 = m0.previewCpText;
    
    // R-A1 Standalone: validator with no prefix
    const m1_s = translator.buildReviewModel(nl, { validator: validator, prefixLines: [] });
    const cp1_s = m1_s.previewCpText;
    
    // R-A1 Contextual: validator with prefix
    const prefix = it.prefix_dsl_blocks;
    const m1_c = translator.buildReviewModel(nl, { validator: validator, prefixLines: prefix });
    const cp1_c = m1_c.previewCpText;
    
    const isComment0 = cp0.startsWith('#');
    if (isComment0) a0_comment_only++;
    else a0_has_instruction++;
    
    if (cp0 !== cp1_s || cp0 !== cp1_c) {
        diff_a0_a1_count++;
        if (diff_a0_a1_count <= 5) {
            console.log(`\nDiff at ${it.item_key} (${it.id}):`);
            console.log('NL:', nl);
            console.log('  A0  :', cp0);
            console.log('  A1_s:', cp1_s);
            console.log('  A1_c:', cp1_c);
        }
    }
});

console.log('\n--- Summary ---');
console.log(`Total items: ${items.length}`);
console.log(`A0 produced instruction code: ${a0_has_instruction}`);
console.log(`A0 comment only (#): ${a0_comment_only}`);
console.log(`Items where A0 differs from A1_s or A1_c: ${diff_a0_a1_count}`);

