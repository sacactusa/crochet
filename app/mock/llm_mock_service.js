/**
 * llm_mock_service.js
 *
 * MOCK LLM Suggestion Service for Mobile App Proof-of-Concept.
 * IMPORTANT: To preserve experimental API quotas, NO real API calls
 * are made from the application. All suggestions are simulated using
 * deterministic template matching.
 */

(function(root) {
    const MOCK_RULES = [
        { pattern: /ch(?:ain)?\s*(\d+)/i, dsl: (m) => `${m[1]}ch` },
        { pattern: /(\d+)\s*sc/i, dsl: (m) => `${m[1]}sc` },
        { pattern: /(\d+)\s*hdc/i, dsl: (m) => `${m[1]}hdc` },
        { pattern: /(\d+)\s*dc/i, dsl: (m) => `${m[1]}dc` },
        { pattern: /turn/i, dsl: () => `turn` },
        { pattern: /fasten off|fo/i, dsl: () => `FO` },
        { pattern: /slip stitch|ss/i, dsl: () => `ss` },
        { pattern: /inc(?:rease)?/i, dsl: () => `2sc` },
        { pattern: /dec(?:rease)?/i, dsl: () => `sc2tog` }
    ];

    function mockTranslate(nlText, config = {}) {
        const text = String(nlText || '').trim();
        if (!text) {
            return {
                dsl: '',
                mocked: true,
                model_placeholder: config.model || 'Gemini 2.5/3.8 (Mocked)',
                reasoning_placeholder: config.reasoning || 'Default',
                simulated_thinking_tokens: config.reasoning === 'ON' || config.reasoning === 'HIGH' ? 1420 : 0,
                latency_ms: 120
            };
        }

        const matchedPieces = [];
        for (const rule of MOCK_RULES) {
            const m = text.match(rule.pattern);
            if (m) {
                matchedPieces.push(rule.dsl(m));
            }
        }

        let dslOutput = matchedPieces.length > 0 ? matchedPieces.join(', ') : `# ${text}`;
        
        return {
            dsl: dslOutput,
            mocked: true,
            model_placeholder: config.model || 'Gemini 2.5/3.8 (Mocked)',
            reasoning_placeholder: config.reasoning || 'Default',
            simulated_thinking_tokens: config.reasoning === 'ON' || config.reasoning === 'HIGH' ? 1420 : 0,
            latency_ms: 120,
            notice: 'Mocked suggestion service (Zero API quota used)'
        };
    }

    root.LLMMockService = {
        translate: mockTranslate
    };
})(typeof window !== 'undefined' ? window : this);

