/**
 * app.js
 *
 * CrochetPARADE Mobile Proof-of-Concept Controller:
 * - On-device Rule-Based Translation (R-A0 and R-A1)
 * - On-device CrochetPARADE Compiler Validator
 * - Syntax error indicator & validity rate calculation
 * - Mock LLM Suggestion Service (Zero API quota used)
 */

(function() {
    // State
    const state = {
        mode: 'R-A1', // 'R-A0', 'R-A1', 'LLM_MOCK'
        steps: [],
        currentInput: '',
        llmModelPlaceholder: 'gemini-2.5-flash (Placeholder)',
        llmReasoningPlaceholder: 'ON (Placeholder)'
    };

    // DOM Elements
    const elements = {
        nlInput: document.getElementById('nl-input'),
        translateBtn: document.getElementById('translate-btn'),
        dslOutput: document.getElementById('dsl-output'),
        compileBtn: document.getElementById('compile-btn'),
        validationBadge: document.getElementById('validation-badge'),
        errorMessage: document.getElementById('error-message'),
        warningMessage: document.getElementById('warning-message'),
        stepsList: document.getElementById('steps-list'),
        validityRateEl: document.getElementById('validity-rate'),
        validStepsCountEl: document.getElementById('valid-steps-count'),
        totalStepsCountEl: document.getElementById('total-steps-count'),
        modeSelect: document.getElementById('translation-mode'),
        llmSettingsCard: document.getElementById('llm-settings-card'),
        sampleSelect: document.getElementById('sample-select'),
        clearBtn: document.getElementById('clear-btn')
    };

    const SAMPLES = [
        { label: "Sample 1 (Chain): With A, ch 16.", text: "With A, ch 16." },
        { label: "Sample 2 (Hdc Row): 1 hdc in each ch to end. Turn.", text: "1 hdc in each ch to end. Turn." },
        { label: "Sample 3 (Round): Ch 1. 20 sc in back loop only. Turn.", text: "Ch 1. 20 sc in back loop only. Turn." },
        { label: "Sample 4 (Complex): Ch 3. 22 dc, 23 dc, 23 dc. Turn.", text: "Ch 3. 22 dc, 23 dc, 23 dc. Turn." },
        { label: "Sample 5 (Invalid Syntax): Work 5 sparkle stitches nowhere.", text: "Work 5 sparkle stitches nowhere." }
    ];

    function init() {
        populateSamples();
        bindEvents();
        updateUI();
    }

    function populateSamples() {
        elements.sampleSelect.innerHTML = '<option value="">-- Pilih Contoh Instruksi CrochetBench --</option>';
        SAMPLES.forEach((s, idx) => {
            const opt = document.createElement('option');
            opt.value = s.text;
            opt.textContent = s.label;
            elements.sampleSelect.appendChild(opt);
        });
    }

    function bindEvents() {
        elements.sampleSelect.addEventListener('change', (e) => {
            if (e.target.value) {
                elements.nlInput.value = e.target.value;
            }
        });

        elements.modeSelect.addEventListener('change', (e) => {
            state.mode = e.target.value;
            elements.llmSettingsCard.style.display = state.mode === 'LLM_MOCK' ? 'block' : 'none';
        });

        elements.translateBtn.addEventListener('click', handleTranslate);
        elements.compileBtn.addEventListener('click', handleManualCompile);
        elements.clearBtn.addEventListener('click', handleClearAll);
    }

    function runLocalCompiler(dslText) {
        if (!dslText || !dslText.trim()) {
            return { valid: false, error: 'Input DSL kosong.' };
        }

        // Clean up warnings array if present
        if (window.WARNINGS) window.WARNINGS.length = 0;
        if (window.WARNED_MESSAGES && window.WARNED_MESSAGES.clear) window.WARNED_MESSAGES.clear();

        try {
            if (typeof window.final !== 'function') {
                return { valid: false, error: 'CrochetPARADE compiler engine (parse64.js) tidak terpasang.' };
            }
            window.final(dslText.trim());
            const warnings = window.WARNINGS ? Array.from(window.WARNINGS) : [];
            return {
                valid: true,
                error: null,
                warnings: warnings
            };
        } catch (err) {
            const warnings = window.WARNINGS ? Array.from(window.WARNINGS) : [];
            return {
                valid: false,
                error: err.message || String(err),
                warnings: warnings
            };
        }
    }

    function handleTranslate() {
        const text = elements.nlInput.value.trim();
        if (!text) {
            alert('Masukkan teks instruksi rajut terlebih dahulu.');
            return;
        }

        let dslResult = '';
        let metadata = {};

        if (state.mode === 'R-A0' || state.mode === 'R-A1') {
            // Local Rule-Based Translator
            if (typeof window.CPDeterministicTranslator === 'undefined' || typeof window.CPDeterministicTranslator.buildReviewModel !== 'function') {
                alert('Modul CPDeterministicTranslator lokal belum siap.');
                return;
            }

            const useValidator = (state.mode === 'R-A1');
            const validatorFunc = useValidator ? (t) => {
                const res = runLocalCompiler(t);
                return { ok: res.valid, error: res.error || '', lastCount: null };
            } : null;

            const m = window.CPDeterministicTranslator.buildReviewModel(text, { validator: validatorFunc });
            dslResult = (m && m.previewCpText) ? m.previewCpText : `# ${text}`;
            metadata = {
                engine: 'Rule-Based (' + state.mode + ')',
                offline: true,
                warnings: m ? m.warnings : []
            };
        } else if (state.mode === 'LLM_MOCK') {
            // Mock LLM Service (Zero API quota consumed)
            const mockRes = window.LLMMockService.translate(text, {
                model: state.llmModelPlaceholder,
                reasoning: state.llmReasoningPlaceholder
            });
            dslResult = mockRes.dsl;
            metadata = {
                engine: 'Mock LLM (Simulated)',
                notice: mockRes.notice,
                simulated_thinking_tokens: mockRes.simulated_thinking_tokens
            };
        }

        elements.dslOutput.value = dslResult;

        // Auto validate the newly generated DSL
        validateAndRecordStep(text, dslResult, metadata);
    }

    function handleManualCompile() {
        const dslText = elements.dslOutput.value.trim();
        if (!dslText) {
            alert('Belum ada kode DSL untuk dikompilasi.');
            return;
        }
        const res = runLocalCompiler(dslText);
        displayValidationResult(res);
    }

    function validateAndRecordStep(nl, dsl, metadata) {
        // Compile against cumulative context
        const allPreviousDsl = state.steps.map(s => s.dsl).join('\n');
        const fullContext = allPreviousDsl ? `${allPreviousDsl}\n${dsl}` : dsl;

        const res = runLocalCompiler(fullContext);
        displayValidationResult(res);

        // Record step
        state.steps.push({
            id: state.steps.length + 1,
            nl: nl,
            dsl: dsl,
            valid: res.valid,
            error: res.error,
            metadata: metadata
        });

        updateUI();
    }

    function displayValidationResult(res) {
        if (res.valid) {
            elements.validationBadge.className = 'badge badge-success';
            elements.validationBadge.textContent = 'KOMPILASI BERHASIL (VALID)';
            elements.errorMessage.style.display = 'none';
        } else {
            elements.validationBadge.className = 'badge badge-danger';
            elements.validationBadge.textContent = 'SYNTAX ERROR (TIDAK VALID)';
            elements.errorMessage.style.display = 'block';
            elements.errorMessage.textContent = 'Compiler Error: ' + res.error;
        }

        if (res.warnings && res.warnings.length > 0) {
            elements.warningMessage.style.display = 'block';
            elements.warningMessage.textContent = 'Peringatan (' + res.warnings.length + '): ' + res.warnings.join('; ');
        } else {
            elements.warningMessage.style.display = 'none';
        }
    }

    function updateUI() {
        const total = state.steps.length;
        const validCount = state.steps.filter(s => s.valid).length;
        const rate = total > 0 ? ((validCount / total) * 100).toFixed(1) : '100.0';

        elements.totalStepsCountEl.textContent = total;
        elements.validStepsCountEl.textContent = validCount;
        elements.validityRateEl.textContent = rate + '%';

        // Render steps list
        elements.stepsList.innerHTML = '';
        if (total === 0) {
            elements.stepsList.innerHTML = '<div class="empty-state">Belum ada langkah instruksi yang ditambahkan.</div>';
            return;
        }

        state.steps.forEach(step => {
            const card = document.createElement('div');
            card.className = 'step-card ' + (step.valid ? 'step-valid' : 'step-invalid');
            card.innerHTML = `
                <div class="step-header">
                    <span class="step-num">Langkah #${step.id}</span>
                    <span class="badge ${step.valid ? 'badge-success' : 'badge-danger'}">
                        ${step.valid ? 'Valid' : 'Error'}
                    </span>
                </div>
                <div class="step-nl"><strong>NL:</strong> ${escapeHtml(step.nl)}</div>
                <div class="step-dsl"><code>${escapeHtml(step.dsl)}</code></div>
                ${step.error ? `<div class="step-err-msg"><small>${escapeHtml(step.error)}</small></div>` : ''}
            `;
            elements.stepsList.appendChild(card);
        });
    }

    function handleClearAll() {
        if (state.steps.length > 0 && !confirm('Hapus seluruh riwayat langkah rajut?')) {
            return;
        }
        state.steps = [];
        elements.nlInput.value = '';
        elements.dslOutput.value = '';
        elements.validationBadge.className = 'badge badge-neutral';
        elements.validationBadge.textContent = 'MENUNGGU INPUT';
        elements.errorMessage.style.display = 'none';
        elements.warningMessage.style.display = 'none';
        updateUI();
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Run on DOM loaded
    document.addEventListener('DOMContentLoaded', init);
})();
