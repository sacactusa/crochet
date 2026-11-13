const fs = require('fs');
const compiler = require('../harness/compiler.js');

const files = [
    { group: 'early', path: 'data/crochetbench_repo/data/step_level_test_1_2.json' },
    { group: 'mid', path: 'data/crochetbench_repo/data/step_level_test_3_4.json' },
    { group: 'late', path: 'data/crochetbench_repo/data/step_level_test_5_6.json' }
];

const empty_ids = new Set(['early_16', 'early_27', 'mid_14', 'mid_24']);

// Let's do two audit runs:
// Run 1: Strict line-by-line starting with 'DSL:' (exact 320 lines)
// Run 2: Grouping multiline blocks (e.g. [...\n]*12) where brackets wrap across lines

const items_119 = [];
for (const { group, path } of files) {
    const data = JSON.parse(fs.readFileSync(path, 'utf8'));
    data.forEach((item, idx) => {
        const gid = `${group}_${idx}`;
        if (empty_ids.has(gid)) return;
        items_119.push({ gid, group, idx, prompt: item.prompt });
    });
}

// RUN 1: Line by line (320 lines)
let run1_total = 0;
let run1_standalone_valid = 0;
let run1_contextual_valid = 0;
const run1_contextual_failures = [];

items_119.forEach(it => {
    const lines = it.prompt.split(/\r?\n/);
    const dslLines = [];
    lines.forEach(l => {
        if (l.startsWith('DSL:')) {
            const val = l.slice(4).trim();
            if (val) dslLines.push(val);
        }
    });

    let prefixAcc = [];
    dslLines.forEach((line, lineIdx) => {
        run1_total++;
        const sRes = compiler.compile(line);
        if (sRes.valid) run1_standalone_valid++;

        prefixAcc.push(line);
        const cRes = compiler.compile(prefixAcc.join('\n'));
        if (cRes.valid) run1_contextual_valid++;
        else run1_contextual_failures.push({ gid: it.gid, lineIdx, line, error: cRes.error });
    });
});

// RUN 2: Handling the 4 multiline repeat blocks where the closing bracket is on the next line
// (mid_27, late_8, late_12, late_22)
let run2_total = 0;
let run2_standalone_valid = 0;
let run2_contextual_valid = 0;
const run2_contextual_failures = [];

items_119.forEach(it => {
    const lines = it.prompt.split(/\r?\n/);
    const dslLines = [];
    for (let i = 0; i < lines.length; i++) {
        const l = lines[i];
        if (l.startsWith('DSL:')) {
            let val = l.slice(4).trim();
            // check if next line is continuation (e.g. ]*12)
            if (i + 1 < lines.length && /^\s*\]\s*\*\s*\d+/.test(lines[i + 1])) {
                val = val + '\n' + lines[i + 1].trim();
                i++;
            }
            if (val) dslLines.push(val);
        }
    }

    let prefixAcc = [];
    dslLines.forEach((line, lineIdx) => {
        run2_total++;
        const sRes = compiler.compile(line);
        if (sRes.valid) run2_standalone_valid++;

        prefixAcc.push(line);
        const cRes = compiler.compile(prefixAcc.join('\n'));
        if (cRes.valid) run2_contextual_valid++;
        else run2_contextual_failures.push({ gid: it.gid, lineIdx, line, error: cRes.error });
    });
});

const output = {
    run1_line_by_line: {
        total: run1_total,
        standalone_valid: run1_standalone_valid,
        standalone_rate: (run1_standalone_valid / run1_total * 100).toFixed(2) + '%',
        contextual_valid: run1_contextual_valid,
        contextual_rate: (run1_contextual_valid / run1_total * 100).toFixed(2) + '%',
        contextual_failures: run1_contextual_failures
    },
    run2_multiline_joined: {
        total: run2_total,
        standalone_valid: run2_standalone_valid,
        standalone_rate: (run2_standalone_valid / run2_total * 100).toFixed(2) + '%',
        contextual_valid: run2_contextual_valid,
        contextual_rate: (run2_contextual_valid / run2_total * 100).toFixed(2) + '%',
        contextual_failures: run2_contextual_failures
    },
    proposal_report: {
        total: 320,
        standalone_valid: 189,
        standalone_rate: '59.06%',
        contextual_valid: 318,
        contextual_rate: '99.38%'
    }
};

fs.writeFileSync('results/audit_replication.json', JSON.stringify(output, null, 2), 'utf8');
console.log(JSON.stringify(output, null, 2));

