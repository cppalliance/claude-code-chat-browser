import { describe, expect, it } from 'vitest';
import { renderFileEditResult } from './file_edit.js';
import { mountToolResult, expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderFileEditResult', () => {
    it('renders edited file path in summary', () => {
        const html = renderFileEditResult({
            result_type: 'file_edit',
            file_path: 'src/app.js',
        });
        expect(html).toContain('Edited: src/app.js');
        expect(html).toContain('tool-result');
    });

    it('handles missing file path', () => {
        const html = renderFileEditResult({ result_type: 'file_edit' });
        expect(html).toContain('Edited:');
        expect(html).not.toContain('undefined');
    });

    it('escapes HTML in file path via registry', () => {
        const html = mountToolResult({
            result_type: 'file_edit',
            file_path: XSS_SCRIPT,
        });
        expectNoRawHtml(html, [XSS_SCRIPT]);
    });
});
