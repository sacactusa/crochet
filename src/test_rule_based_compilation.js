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

let a0_valid_standalone = 0;
let a0_valid_contextual = 0;

items.forEach(it => {
    const nl = it.target_nl;
    const m0 = translator.buildReviewModel(nl, { validator: null });
    const cp = m0.previewCpText;
    
    // Check if compiler compiles cp standalone
    const s_res = compiler.compile(cp);
    if (s_res.valid) a0_valid_standalone++;
    
    // Check if compiler compiles cp contextual
    const prefix = it.prefix_dsl_context;
    const full_c = prefix ? prefix + '\n' + cp : cp;
    const c_res = compiler.compile(full_c);
    if (c_res.valid) a0_valid_contextual++;
});

console.log(`Total items: ${items.length}`);
console.log(`Standalone valid: ${a0_valid_standalone} / ${items.length} (${(a0_valid_standalone/items.length*100).toFixed(2)}%)`);
console.log(`Contextual valid: ${a0_valid_contextual} / ${items.length} (${(a0_valid_contextual/items.length*100).toFixed(2)}%)`);

