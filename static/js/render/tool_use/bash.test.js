import { describe, expect, it } from 'vitest';
import { renderBashUse } from './bash.js';

describe('renderBashUse', () => {
    it('renders command text in the tool body', () => {
        const html = renderBashUse({
            name: 'Bash',
            input: { command: 'ls -la', description: 'list files' },
        });
        expect(html).toContain('ls -la');
        expect(html).toContain('list files');
        expect(html).toContain('tool-call');
    });

    it('escapes HTML in the command', () => {
        const html = renderBashUse({
            name: 'Bash',
            input: { command: '<rm -rf />' },
        });
        expect(html).not.toContain('<rm');
        expect(html).toContain('&lt;rm');
    });
});
