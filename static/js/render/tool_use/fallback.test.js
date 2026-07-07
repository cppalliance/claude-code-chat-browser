import { describe, expect, it } from 'vitest';
import { renderToolUseFallback } from './fallback.js';
import { mountToolUse, expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderToolUseFallback', () => {
    it('renders unknown tool name and JSON input', () => {
        const html = renderToolUseFallback({
            name: 'CustomTool',
            input: { key: 'value', count: 3 },
        });
        expect(html).toContain('Unknown tool: CustomTool');
        expect(html).toContain('&quot;key&quot;');
        expect(html).toContain('value');
        expect(html).toContain('tool-call');
    });

    it('uses unknown dispatch key when name is missing', () => {
        const html = renderToolUseFallback({ input: {} });
        expect(html).toContain('Unknown tool:');
        expect(html).toContain('tool-call');
    });

    it('escapes HTML in JSON fallback body', () => {
        const html = mountToolUse({
            name: 'MysteryTool',
            input: { payload: XSS_SCRIPT },
        });
        expectNoRawHtml(html, [XSS_SCRIPT]);
        expect(html).toContain('&lt;script&gt;');
    });
});
