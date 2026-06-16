import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('hljs-theme-init.js', () => {
    beforeEach(() => {
        vi.resetModules();
        document.documentElement.setAttribute('data-theme', 'dark');
        document.body.innerHTML = '';
    });

    it('does nothing when data-theme is dark', async () => {
        document.body.innerHTML = '<link id="hljs-theme" href="https://example.com/dark.css" />';
        await import('./hljs-theme-init.js');
        const link = document.getElementById('hljs-theme');
        expect(link.href).toContain('dark.css');
        expect(link.getAttribute('integrity')).toBeNull();
    });

    it('sets light-theme CDN href and SRI when data-theme is light', async () => {
        document.documentElement.setAttribute('data-theme', 'light');
        document.body.innerHTML = '<link id="hljs-theme" href="about:blank" />';
        await import('./hljs-theme-init.js');
        const link = document.getElementById('hljs-theme');
        expect(link.href).toContain('github.min.css');
        expect(link.integrity).toBe(
            'sha512-0aPQyyeZrWj9sCA46UlmWgKOP0mUipLQ6OZXu8l4IcAmD2u31EPEy9VcIMvl7SoAaKe8bLXZhYoMaE/in+gcgA==',
        );
    });

    it('no-ops when hljs-theme link is missing', async () => {
        document.documentElement.setAttribute('data-theme', 'light');
        await import('./hljs-theme-init.js');
        expect(document.getElementById('hljs-theme')).toBeNull();
    });
});
