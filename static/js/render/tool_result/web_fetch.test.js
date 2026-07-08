import { describe, expect, it } from 'vitest';
import { renderWebFetchResult } from './web_fetch.js';
import { renderToolResult } from '../registry.js';
import { expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderWebFetchResult', () => {
    it('renders url and status code in summary', () => {
        const html = renderWebFetchResult({
            result_type: 'web_fetch',
            url: 'https://example.com/page',
            status_code: 200,
        });
        expect(html).toContain('Fetch: https://example.com/page');
        expect(html).toContain('(200)');
        expect(html).toContain('tool-result');
    });

    it('shows question mark when status code is absent', () => {
        const html = renderWebFetchResult({
            result_type: 'web_fetch',
            url: 'https://example.com',
        });
        expect(html).toContain('(?)');
    });

    it('escapes HTML in url via registry', () => {
        const html = renderToolResult({
            result_type: 'web_fetch',
            url: XSS_SCRIPT,
            status_code: 404,
        });
        expectNoRawHtml(html, [XSS_SCRIPT]);
    });
});
