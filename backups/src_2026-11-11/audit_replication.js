const fs = require('fs');
const vm = require('vm');

// Load parse64
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

// Load dataset
const files = [
    { group: 'early', path: 'data/crochetbench_repo/data/step_level_test_1_2.json' },
    { group: 'mid', path: 'data/crochetbench_repo/data/step_level_test_3_4.json' },
    { group: 'late', path: 'data/crochetbench_repo/data/step_level_test_5_6.json' }
];

const empty_ids = new Set(['early_16', 'early_27', 'mid_14', 'mid_24']);

let totalDslLines = 0;
let standaloneValid = 0;
let contextualValid = 0;

const details = [];

for (const { group, path } of files) {
    const data = JSON.parse(fs.readFileSync(path, 'utf8'));
    data.forEach((item, idx) => {
        const gid = `${group}_${idx}`;
        if (empty_ids.has(gid)) return;
        
        const prompt = item.prompt || '';
        const lines = prompt.split(/\r?\n/);
        const itemDsls = [];
        for (const l of lines) {
            if (l.startsWith('DSL:')) {
                const val = l.slice(4).trim();
                if (val) itemDsls.push(val);
            }
        }
        
        let prefixAcc = [];
        itemDsls.forEach((dsl, dslIdx) => {
            totalDslLines++;
            
            // Standalone
            const sRes = compile(dsl);
            if (sRes.valid) standaloneValid++;
            
            // Contextual
            prefixAcc.push(dsl);
            const cRes = compile(prefixAcc.join('\n'));
            if (cRes.valid) contextualValid++;
            else {
                details.push({ gid, dslIdx, dsl, err: cRes.error });
            }
        });
    });
}

console.log(`Total DSL lines: ${totalDslLines}`);
console.log(`Standalone valid: ${standaloneValid}/${totalDslLines} (${(standaloneValid/totalDslLines*100).toFixed(2)}%)`);
console.log(`Contextual valid: ${contextualValid}/${totalDslLines} (${(contextualValid/totalDslLines*100).toFixed(2)}%)`);
console.log('Contextual failures count:', details.length);
details.forEach(d => console.log(`  Fail: ${d.gid} [${d.dslIdx}] -> ${d.dsl} | Err: ${d.err}`));

