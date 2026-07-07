import { describe, expect, it } from 'vitest';
import { renderGrepUse } from './grep.js';
import { mountToolUse, expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderGrepUse', () => {
    it('renders pattern and optional path', () => {
        const html = renderGrepUse({
            name: 'Grep',
            input: { pattern: 'TODO', path: 'lib/' },
        });
        expect(html).toContain('TODO');
        expect(html).toContain('lib/');
        expect(html).toContain('tool-call');
    });

    it('renders pattern only when path is absent', () => {
        const html = renderGrepUse({
            name: 'Grep',
            input: { pattern: 'error' },
        });
        expect(html).toContain('error');
        expect(html).not.toContain(' in <code>');
    });

    it('escapes HTML in pattern and path', () => {
        const html = mountToolUse({
            name: 'Grep',
            input: { pattern: XSS_SCRIPT, path: '<root>' },
        });
        expectNoRawHtml(html, [XSS_SCRIPT, '<root>']);
    });
});
