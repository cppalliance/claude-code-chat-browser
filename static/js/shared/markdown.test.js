import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { cleanContent, renderMarkdown } from './markdown.js';

const _origMarked = globalThis.marked;
const _origDOMPurify = globalThis.DOMPurify;

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
        globalThis.marked = marked;
        globalThis.DOMPurify = DOMPurify;
    });

    afterEach(() => {
        globalThis.marked = _origMarked;
        globalThis.DOMPurify = _origDOMPurify;
    });

    it('sanitizes script tags from parsed output', () => {
        const sanitizeSpy = vi.spyOn(DOMPurify, 'sanitize');
        const html = renderMarkdown('# Hello\n\n<script>alert(1)</script>');
        expect(sanitizeSpy).toHaveBeenCalled();
        expect(html).not.toContain('<script');
        expect(html).not.toMatch(/alert\s*\(/);
        sanitizeSpy.mockRestore();
    });

    it('strips event handlers from parsed output', () => {
        const sanitizeSpy = vi.spyOn(DOMPurify, 'sanitize');
        const html = renderMarkdown('<img src=x onerror=alert(1)>');
        expect(sanitizeSpy).toHaveBeenCalled();
        expect(html).not.toMatch(/onerror/i);
        sanitizeSpy.mockRestore();
    });

    it('falls back to inline code when marked is unavailable', () => {
        delete globalThis.marked;
        const html = renderMarkdown('`code`');
        expect(html).toBe('<code>code</code>');
    });

    it('falls back to escaped output when DOMPurify is unavailable', () => {
        delete globalThis.DOMPurify;
        const html = renderMarkdown('Hello **world**');
        expect(html).toBeDefined();
        expect(html).toContain('Hello');
        expect(html).toContain('**world**');
        expect(html).not.toMatch(/<script/i);
    });
});
