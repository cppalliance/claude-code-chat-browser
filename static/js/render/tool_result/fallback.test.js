import { describe, expect, it } from 'vitest';
import { renderToolResultFallback } from './fallback.js';
import { mountToolResult, expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderToolResultFallback', () => {
    it('renders unknown result type and JSON payload', () => {
        const html = renderToolResultFallback({
            result_type: 'custom_widget',
            widget_id: 99,
            label: 'test',
        });
        expect(html).toContain('Unknown tool result: custom_widget');
        expect(html).toContain('&quot;widget_id&quot;');
        expect(html).toContain('99');
        expect(html).toContain('tool-result');
    });

    it('uses unknown dispatch key when result_type is missing', () => {
        const html = renderToolResultFallback({ payload: 'data' });
        expect(html).toContain('Unknown tool result:');
        expect(html).toContain('tool-result');
    });

    it('escapes HTML in JSON fallback body', () => {
        const html = mountToolResult({
            result_type: 'mystery',
            content: XSS_SCRIPT,
        });
        expectNoRawHtml(html, [XSS_SCRIPT]);
        expect(html).toContain('&lt;script&gt;');
    });
});
