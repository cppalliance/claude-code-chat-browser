import { describe, expect, it } from 'vitest';
import { renderFileReadResult } from './file_read.js';

describe('renderFileReadResult', () => {
    it('renders file path and line count in the summary', () => {
        const html = renderFileReadResult({
            result_type: 'file_read',
            file_path: '/src/main.cpp',
            num_lines: 42,
        });
        expect(html).toContain('/src/main.cpp');
        expect(html).toContain('42 lines');
        expect(html).toContain('tool-result');
    });

    it('omits line count when num_lines is absent', () => {
        const html = renderFileReadResult({
            result_type: 'file_read',
            file_path: 'README.md',
        });
        expect(html).toContain('Read: README.md');
        expect(html).not.toMatch(/\d+ lines/);
    });
});
