import { describe, expect, it } from 'vitest';
import { renderGrepResult } from './grep.js';

describe('renderGrepResult', () => {
    it('renders file and line counts in summary', () => {
        const html = renderGrepResult({
            result_type: 'grep',
            num_files: 5,
            num_lines: 42,
        });
        expect(html).toContain('Grep: 5 files, 42 lines');
        expect(html).toContain('tool-result');
    });

    it('defaults counts to zero when absent', () => {
        const html = renderGrepResult({ result_type: 'grep' });
        expect(html).toContain('Grep: 0 files, 0 lines');
    });
});
