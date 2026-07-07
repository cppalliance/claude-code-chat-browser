import { describe, expect, it } from 'vitest';
import { renderWebSearchResult } from './web_search.js';
import { mountToolResult, expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderWebSearchResult', () => {
    it('renders query and result count in summary', () => {
        const html = renderWebSearchResult({
            result_type: 'web_search',
            query: 'vitest coverage',
            result_count: 8,
        });
        expect(html).toContain('Search: &quot;vitest coverage&quot;');
        expect(html).toContain('8 results');
        expect(html).toContain('tool-result');
    });

    it('handles missing query and count', () => {
        const html = renderWebSearchResult({ result_type: 'web_search' });
        expect(html).toContain('Search: &quot;&quot;');
        expect(html).toContain('0 results');
    });

    it('escapes HTML in query via registry', () => {
        const html = mountToolResult({
            result_type: 'web_search',
            query: XSS_SCRIPT,
            result_count: 1,
        });
        expectNoRawHtml(html, [XSS_SCRIPT]);
    });
});
