const fs = require('fs');
const path = require('path');
const vm = require('vm');

console.log("=== TESTING BROWSER INTEGRATION ===");

const parse64Code = fs.readFileSync(path.join(__dirname, 'engine', 'parse64.js'), 'utf8');
const translatorCode = fs.readFileSync(path.join(__dirname, 'engine', 'deterministic_translator.js'), 'utf8');

const ctx = {
    console: console,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    alert: () => {}
};
ctx.window = ctx;
ctx.globalThis = ctx;
ctx.root = ctx;

vm.runInNewContext(parse64Code, ctx);
vm.runInNewContext(translatorCode, ctx);

const translator = ctx.CPDeterministicTranslator;
console.log("Translator loaded:", !!translator);

// Validator function
const validator = (dslText) => {
    try {
        ctx.final(dslText);
        return { ok: true, error: "" };
    } catch (e) {
        return { ok: false, error: e.message || String(e) };
    }
};

// Test R-A0 (no validator)
const resA0 = translator.buildStaticReviewModel("ch 16", { validator: null });
console.log("R-A0 Translation ('ch 16'):", resA0.previewCpText);

// Test R-A1 (with validator)
const resA1 = translator.buildStaticReviewModel("ch 16", { validator: validator });
console.log("R-A1 Translation ('ch 16'):", resA1.previewCpText);

