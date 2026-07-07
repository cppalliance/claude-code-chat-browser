import { expect } from 'vitest';
import { renderToolUse, renderToolResult } from './registry.js';

/** Common XSS payloads for renderer escaping assertions. */
export const XSS_SCRIPT = '<script>alert(1)</script>';
export const XSS_IMG = '<img onerror=alert(1)>';

/**
 * Render a tool-use card via the registry and return the HTML string.
 */
export function mountToolUse(tool) {
    return renderToolUse(tool);
}

/**
 * Render a tool-result card via the registry and return the HTML string.
 */
export function mountToolResult(parsed) {
    return renderToolResult(parsed);
}

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
