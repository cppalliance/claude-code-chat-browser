import { describe, expect, it } from 'vitest';
import { renderGlobUse } from './glob.js';
import { renderToolUse } from '../registry.js';
import { expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderGlobUse', () => {
    it('renders pattern and optional path', () => {
        const html = renderGlobUse({
            name: 'Glob',
            input: { pattern: '**/*.js', path: 'src/' },
        });
        expect(html).toContain('**/*.js');
        expect(html).toContain('src/');
        expect(html).toContain('tool-call');
    });

    it('renders pattern only when path is absent', () => {
        const html = renderGlobUse({
            name: 'Glob',
            input: { pattern: '*.py' },
        });
        expect(html).toContain('*.py');
        expect(html).not.toContain(' in <code>');
    });

    it('escapes HTML in pattern and path', () => {
        const html = renderToolUse({
            name: 'Glob',
            input: { pattern: XSS_SCRIPT, path: '<evil>/' },
        });
        expectNoRawHtml(html, [XSS_SCRIPT, '<evil>']);
    });
});
