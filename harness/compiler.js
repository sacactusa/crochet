/**
 * Headless CrochetPARADE Compiler Harness
 * Uses parse64.js from commit be11c8b0a37f2fdeaca39bd2c1cd2b0cc7fc281d
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const parse64Path = path.join(__dirname, 'crochetparade', 'parse64.js');
if (!fs.existsSync(parse64Path)) {
    throw new Error(`Cannot find parse64.js at ${parse64Path}`);
}
const parse64Code = fs.readFileSync(parse64Path, 'utf8');

function createCompilerContext() {
    let capturedAlerts = [];
    const ctx = {
        console: console,
        setTimeout: setTimeout,
        clearTimeout: clearTimeout,
        alert: (msg) => {
            capturedAlerts.push(String(msg));
        },
        document: {
            getElementById: () => null,
            createElement: () => ({ appendChild: () => {}, style: {} }),
            createTextNode: () => ({}),
            querySelector: () => null,
            querySelectorAll: () => []
        }
    };
    ctx.window = ctx;
    ctx.globalThis = ctx;
    ctx.root = ctx;

    vm.runInNewContext(parse64Code, ctx);

    return {
        compile: (dslText) => {
            capturedAlerts = [];
            if (ctx.WARNINGS) ctx.WARNINGS.length = 0;
            if (ctx.WARNED_MESSAGES && ctx.WARNED_MESSAGES.clear) ctx.WARNED_MESSAGES.clear();

            const text = String(dslText || '').trim();
            if (!text) {
                return {
                    valid: false,
                    error: 'Empty DSL input',
                    warningsCount: 0,
                    warnings: []
                };
            }

            try {
                ctx.final(text);
                const warnings = ctx.WARNINGS ? Array.from(ctx.WARNINGS) : [];
                return {
                    valid: true,
                    error: null,
                    warningsCount: warnings.length,
                    warnings: warnings
                };
            } catch (err) {
                const warnings = ctx.WARNINGS ? Array.from(ctx.WARNINGS) : [];
                return {
                    valid: false,
                    error: err.message || String(err),
                    warningsCount: warnings.length,
                    warnings: warnings
                };
            }
        }
    };
}

const defaultCompiler = createCompilerContext();

function compile(dslText) {
    return defaultCompiler.compile(dslText);
}

module.exports = {
    compile,
    createCompilerContext
};

// If run from CLI
if (require.main === module) {
    const inputArg = process.argv[2];
    if (!inputArg) {
        let stdinData = '';
        process.stdin.setEncoding('utf8');
        process.stdin.on('data', chunk => stdinData += chunk);
        process.stdin.on('end', () => {
            const res = compile(stdinData);
            console.log(JSON.stringify(res, null, 2));
            process.exit(res.valid ? 0 : 1);
        });
    } else if (fs.existsSync(inputArg)) {
        const content = fs.readFileSync(inputArg, 'utf8');
        const res = compile(content);
        console.log(JSON.stringify(res, null, 2));
        process.exit(res.valid ? 0 : 1);
    } else {
        const res = compile(inputArg);
        console.log(JSON.stringify(res, null, 2));
        process.exit(res.valid ? 0 : 1);
    }
}

