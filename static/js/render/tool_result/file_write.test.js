import { describe, expect, it } from 'vitest';
import { renderFileWriteResult } from './file_write.js';
import { renderToolResult } from '../registry.js';
import { expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderFileWriteResult', () => {
    it('renders written file path in summary', () => {
        const html = renderFileWriteResult({
            result_type: 'file_write',
            file_path: 'output/data.json',
        });
        expect(html).toContain('Wrote: output/data.json');
        expect(html).toContain('tool-result');
    });

    it('handles missing file path', () => {
        const html = renderFileWriteResult({ result_type: 'file_write' });
        expect(html).toContain('Wrote:');
        expect(html).not.toContain('undefined');
    });

    it('escapes HTML in file path via registry', () => {
        const html = renderToolResult({
            result_type: 'file_write',
            file_path: XSS_SCRIPT,
        });
        expectNoRawHtml(html, [XSS_SCRIPT]);
    });
});
