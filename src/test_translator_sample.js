const fs = require('fs');
const vm = require('vm');
const compiler = require('../harness/compiler.js');

let src = fs.readFileSync('harness/crochetparade/deterministic_translator.js', 'utf8');
src = src.replace('buildStaticReviewModel,', 'buildStaticReviewModel,\n    buildReviewModel,');
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

for (let i = 0; i < 5; i++) {
    const it = items[i];
    console.log(`\n=== Item ${it.item_key} (${it.id}) ===`);
    console.log('Target NL:', it.target_nl);
    
    // A0 (no validator)
    const m0 = translator.buildReviewModel(it.target_nl, { validator: null });
    console.log('A0 previewCpText:\n' + m0.previewCpText);
    
    // A1 standalone (validator, no prefix)
    const m1_s = translator.buildReviewModel(it.target_nl, { validator: validator, prefixLines: [] });
    console.log('A1 Standalone previewCpText:\n' + m1_s.previewCpText);
    
    // A1 contextual (validator with prefix)
    const prefix = it.prefix_dsl_blocks;
    const m1_c = translator.buildReviewModel(it.target_nl, { validator: validator, prefixLines: prefix });
    console.log('A1 Contextual previewCpText:\n' + m1_c.previewCpText);
}

