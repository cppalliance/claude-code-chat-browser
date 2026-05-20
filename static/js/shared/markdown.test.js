import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cleanContent, renderMarkdown } from './markdown.js';

describe('cleanContent', () => {
    it('strips system-reminder blocks', () => {
        const raw = 'Hello<system-reminder>secret</system-reminder> world';
        expect(cleanContent(raw)).toBe('Hello world');
    });

    it('returns empty string for falsy input', () => {
        expect(cleanContent('')).toBe('');
    });
});

describe('renderMarkdown', () => {
    beforeEach(() => {
        globalThis.marked = {
            parse: vi.fn((text) => `<p>${text}</p>`),
        };
        globalThis.DOMPurify = {
            sanitize: vi.fn((html) => html.replace(/<script[\s\S]*?<\/script>/gi, '')),
        };
    });

    it('sanitizes script tags from parsed output', () => {
        globalThis.marked.parse.mockReturnValue('<p>ok</p><script>alert(1)</script>');
        const html = renderMarkdown('# Hello');
        expect(html).not.toContain('<script');
    });

    it('falls back to inline code when marked is unavailable', () => {
        delete globalThis.marked;
        const html = renderMarkdown('`code`');
        expect(html).toBe('<code>code</code>');
    });
});
