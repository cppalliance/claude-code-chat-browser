import { describe, expect, it } from 'vitest';
import { renderToolResult } from './registry.js';

/** Common XSS payloads for renderer escaping assertions. */
export const XSS_SCRIPT = '<script>alert(1)</script>';
export const XSS_IMG = '<img onerror=alert(1)>';

/**
 * Assert raw HTML fragments are escaped (not present verbatim).
 */
export function expectNoRawHtml(html, rawFragments) {
    for (const frag of rawFragments) {
        expect(html).not.toContain(frag);
    }
}

/**
 * Assert an HTML-escaped fragment appears in output.
 */
export function expectEscaped(html, escapedFragment) {
    expect(html).toContain(escapedFragment);
}

/**
 * Shared behavioral tests for summary-only tool_result renderers (Edited/Plan/Wrote).
 */
export function describeSummaryOnlyResult(
    render,
    { suiteName, resultType, label, samplePath },
) {
    describe(suiteName, () => {
        it(`renders ${label.toLowerCase()} file path in summary`, () => {
            const html = render({ result_type: resultType, file_path: samplePath });
            expect(html).toContain(`${label}: ${samplePath}`);
            expect(html).toContain('tool-result');
        });

        it('handles missing file path', () => {
            const html = render({ result_type: resultType });
            expect(html).toContain(`${label}:`);
            expect(html).not.toContain('undefined');
        });

        it('escapes HTML in file path via registry', () => {
            const html = renderToolResult({
                result_type: resultType,
                file_path: XSS_SCRIPT,
            });
            expectNoRawHtml(html, [XSS_SCRIPT]);
        });
    });
}
