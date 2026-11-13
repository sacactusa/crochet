/**
 * test_app_components.js
 * Unit test for mobile app core components: local compiler, translator, and mock service.
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

console.log("=== UNIT TEST: MOBILE APP COMPONENTS ===");

// 1. Test Compiler Engine
const parse64Code = fs.readFileSync(path.join(__dirname, 'engine', 'parse64.js'), 'utf8');
const ctx = { console: console, setTimeout: setTimeout, clearTimeout: clearTimeout, alert: () => {} };
ctx.window = ctx;
ctx.globalThis = ctx;
ctx.root = ctx;
vm.runInNewContext(parse64Code, ctx);

let compilerOk = false;
try {
    ctx.final("16ch, turn");
    compilerOk = true;
} catch (e) {
    compilerOk = false;
}
console.log(`1. Local parse64.js compiler test ("16ch, turn"): ${compilerOk ? "PASS (Valid)" : "FAIL"}`);

let errorCaught = false;
try {
    ctx.final("invalid_crochet_xyz");
} catch (e) {
    errorCaught = true;
}
console.log(`2. Local parse64.js error detection test ("invalid_crochet_xyz"): ${errorCaught ? "PASS (Error caught)" : "FAIL"}`);

// 2. Test Translator Engine
const translatorCode = fs.readFileSync(path.join(__dirname, 'engine', 'deterministic_translator.js'), 'utf8');
vm.runInNewContext(translatorCode, ctx);
let translatorOk = false;
if (ctx.deterministic_translator && typeof ctx.deterministic_translator.translate === 'function') {
    const candidates = ctx.deterministic_translator.translate("ch 16");
    if (candidates && candidates.length > 0) {
        translatorOk = true;
        console.log(`3. Local deterministic_translator.js test ("ch 16"): PASS -> "${candidates[0].dsl}"`);
    }
}
if (!translatorOk) {
    console.log("3. Local deterministic_translator.js test: FAIL");
}

// 3. Test Mock LLM Service
const mockCode = fs.readFileSync(path.join(__dirname, 'mock', 'llm_mock_service.js'), 'utf8');
vm.runInNewContext(mockCode, ctx);
let mockOk = false;
if (ctx.LLMMockService && typeof ctx.LLMMockService.translate === 'function') {
    const mockRes = ctx.LLMMockService.translate("1 hdc in each ch. Turn.");
    if (mockRes.dsl && mockRes.mocked) {
        mockOk = true;
        console.log(`4. Mock LLM Suggestion Service test: PASS -> "${mockRes.dsl}" (Zero API quota used)`);
    }
}
if (!mockOk) {
    console.log("4. Mock LLM Suggestion Service test: FAIL");
}

console.log("=== ALL MOBILE APP COMPONENT TESTS FINISHED ===");

