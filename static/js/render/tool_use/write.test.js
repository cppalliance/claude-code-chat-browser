import { describe, expect, it } from 'vitest';
import { renderWriteUse } from './write.js';
import { mountToolUse, expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderWriteUse', () => {
    it('renders file path and content preview', () => {
        const html = renderWriteUse({
            name: 'Write',
            input: { file_path: 'out.txt', content: 'hello world' },
        });
        expect(html).toContain('out.txt');
        expect(html).toContain('hello world');
        expect(html).toContain('Content');
        expect(html).toContain('tool-call');
    });

    it('omits content section when content is absent', () => {
        const html = renderWriteUse({
            name: 'Write',
            input: { file_path: 'empty.txt' },
        });
        expect(html).toContain('empty.txt');
        expect(html).not.toContain('Content');
    });

    it('escapes HTML in file path and content', () => {
        const html = mountToolUse({
            name: 'Write',
            input: { file_path: XSS_SCRIPT, content: '<bad>payload</bad>' },
        });
        expectNoRawHtml(html, [XSS_SCRIPT, '<bad>']);
        expect(html).toContain('&lt;bad&gt;');
    });
});
