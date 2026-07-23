/**
 * Part A — Golden-parity: JS renderer path for the adversarial bash tool_result.
 *
 * The Python md-exporter path is covered by
 * ``tests/test_dual_path_parity_oracle.py``.  Both suites use the same
 * adversarial payload (``<img src=x onerror=alert(1)>``).
 *
 * These tests drive the **real** JS dispatch path via ``renderToolResult``
 * (registry.js) and the direct renderer ``renderBashResult`` (bash.js) — no
 * reimplementations.
 *
 * Oracle discipline (test-review C3/C8/C9):
 *   Every assertion checks the real observable HTML output, never merely that
 *   the function does not throw.
 */

import { describe, it, expect } from 'vitest';
import { renderToolResult } from '../registry.js';
import { renderBashResult } from './bash.js';

// Shared adversarial payload — must match the Python constant in
// tests/test_dual_path_parity_oracle.py.
const PAYLOAD = '<img src=x onerror=alert(1)>';

// Hand-built parsed shape for the JS renderer only. Classification and fields from
// ``_parse_tool_result`` are asserted in tests/test_dual_path_parity_oracle.py;
// this file will not catch drift if the Python bash builder changes key names.
const ADVERSARIAL_PARSED = {
    result_type: 'bash',
    slug: null,
    stdout: PAYLOAD,
    stderr: '',
    exit_code: 0,
    interrupted: false,
    is_error: false,
    return_code_interpretation: 'success',
};

describe('Part A: golden-parity — adversarial bash result (JS renderer path)', () => {
    it('renders a non-empty HTML string for the adversarial payload', () => {
        // Oracle: output must not be empty — the payload is not silently dropped.
        const html = renderToolResult(ADVERSARIAL_PARSED);
        expect(typeof html).toBe('string');
        expect(html.length).toBeGreaterThan(0);
    });

    it('HTML-escapes the adversarial payload — raw XSS tag must not appear', () => {
        // Oracle: the raw ``<img src=x onerror=`` string must be absent (escaped);
        // the HTML-entity form must be present.
        //
        // Negative control: if esc() were removed from renderBashResult, the raw
        // tag WOULD appear in the output and ``not.toContain`` would fail —
        // a regressed renderer cannot pass this test.
        const html = renderToolResult(ADVERSARIAL_PARSED);
        expect(html).not.toContain('<img src=x onerror=');
        expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;');
    });

    it('routes through the real renderBashResult dispatch path — no re-implementation', () => {
        // Driving both the registry dispatch (renderToolResult) and the direct
        // renderer (renderBashResult) confirms they produce the same output.
        // If registry.js ever wired a different renderer for result_type 'bash',
        // this equality assertion would fail.
        const viaRegistry = renderToolResult(ADVERSARIAL_PARSED);
        const viaDirect = renderBashResult(ADVERSARIAL_PARSED);
        expect(viaRegistry).toBe(viaDirect);
    });

    it('negative control: the raw payload is a dangerous string without escaping', () => {
        // Documents why esc() is load-bearing: PAYLOAD itself contains the
        // executable XSS vector.  If the renderer passed it through unchanged,
        // the browser could execute it.
        expect(PAYLOAD).toContain('<img');
        expect(PAYLOAD).toContain('onerror=');
        expect(PAYLOAD).not.toContain('&lt;');

        // The renderer must NOT pass PAYLOAD through unchanged.
        const html = renderBashResult(ADVERSARIAL_PARSED);
        expect(html).not.toContain(PAYLOAD);
        expect(html).toContain('&lt;');
    });
});
