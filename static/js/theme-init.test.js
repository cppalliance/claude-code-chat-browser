import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('theme-init.js', () => {
    beforeEach(() => {
        vi.resetModules();
        localStorage.clear();
        document.documentElement.removeAttribute('data-theme');
    });

    it('defaults to dark when localStorage has no theme', async () => {
        await import('./theme-init.js');
        expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    });

    it('applies saved light theme before paint', async () => {
        localStorage.setItem('theme', 'light');
        await import('./theme-init.js');
        expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    });

    it('ignores invalid stored theme values', async () => {
        localStorage.setItem('theme', 'sepia');
        await import('./theme-init.js');
        expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    });
});
