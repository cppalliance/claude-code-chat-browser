import { describe, expect, it } from 'vitest';
import { renderGlobResult } from './glob.js';

describe('renderGlobResult', () => {
    it('renders file count in summary', () => {
        const html = renderGlobResult({
            result_type: 'glob',
            num_files: 12,
        });
        expect(html).toContain('Glob: 12 files found');
        expect(html).toContain('tool-result');
    });

    it('shows truncated flag when set', () => {
        const html = renderGlobResult({
            result_type: 'glob',
            num_files: 100,
            truncated: true,
        });
        expect(html).toContain('(truncated)');
    });

    it('defaults to zero files when num_files is absent', () => {
        const html = renderGlobResult({ result_type: 'glob' });
        expect(html).toContain('Glob: 0 files found');
    });
});
