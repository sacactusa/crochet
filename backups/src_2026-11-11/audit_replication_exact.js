const fs = require('fs');
const vm = require('vm');

const context = {
    console: console,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    alert: () => {},
    document: {
        getElementById: () => null,
        createElement: () => ({ appendChild: () => {}, style: {} }),
        createTextNode: () => ({}),
        querySelector: () => null,
        querySelectorAll: () => []
    }
};
context.window = context;
context.globalThis = context;
context.root = context;

const parserCode = fs.readFileSync('harness/crochetparade/parse64.js', 'utf8');
vm.runInNewContext(parserCode, context);

function compile(pattern) {
    try {
        context.final(pattern);
        return { valid: true };
    } catch (e) {
        return { valid: false, error: e.message };
    }
}

const files = [
    { group: 'early', path: 'data/crochetbench_repo/data/step_level_test_1_2.json' },
    { group: 'mid', path: 'data/crochetbench_repo/data/step_level_test_3_4.json' },
    { group: 'late', path: 'data/crochetbench_repo/data/step_level_test_5_6.json' }
];

const empty_ids = new Set(['early_16', 'early_27', 'mid_14', 'mid_24']);

// Let's extract the reference DSL blocks exactly as the author did.
// Notice in the prompts, each example step has 'NL: ...' and 'DSL: ...'
// When a DSL block spans multiple lines (e.g. [...\n]*12), it extends until the next '\nNL:' or '\nNow translate'
let totalDslBlocks = 0;
let standaloneValid = 0;
let contextualValid = 0;

const contextualFailures = [];

for (const { group, path } of files) {
    const data = JSON.parse(fs.readFileSync(path, 'utf8'));
    data.forEach((item, idx) => {
        const gid = `${group}_${idx}`;
        if (empty_ids.has(gid)) return;
        
        const prompt = item.prompt || '';
        
        // Extract all example DSL blocks before the target instruction
        const prefixSection = prompt.split('Now translate the NL into DSL:')[0];
        // Split by NL:
        const parts = prefixSection.split(/\nNL:|^NL:/);
        const itemDsls = [];
        for (const p of parts) {
            if (p.includes('DSL:')) {
                const dslPart = p.split('DSL:')[1].trim();
                if (dslPart) itemDsls.push(dslPart);
            }
        }
        
        let prefixAcc = [];
        itemDsls.forEach((dsl, dslIdx) => {
            totalDslBlocks++;
            
            // Standalone
            const sRes = compile(dsl);
            if (sRes.valid) standaloneValid++;
            
            // Contextual
            prefixAcc.push(dsl);
            const cRes = compile(prefixAcc.join('\n'));
            if (cRes.valid) contextualValid++;
            else {
                contextualFailures.push({ gid, dslIdx, dsl, err: cRes.error });
            }
        });
    });
}

console.log(`Total DSL blocks: ${totalDslBlocks}`);
console.log(`Standalone valid: ${standaloneValid}/${totalDslBlocks} (${(standaloneValid/totalDslBlocks*100).toFixed(2)}%)`);
console.log(`Contextual valid: ${contextualValid}/${totalDslBlocks} (${(contextualValid/totalDslBlocks*100).toFixed(2)}%)`);
console.log('Contextual failures count:', contextualFailures.length);
contextualFailures.forEach(d => console.log(`  Fail: ${d.gid} [${d.dslIdx}] -> ${d.dsl} | Err: ${d.err}`));

