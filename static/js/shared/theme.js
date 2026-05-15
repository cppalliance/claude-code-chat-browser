// Highlight.js theme stylesheets, keyed by theme name. Both `href` and
// `integrity` MUST be assigned together when swapping at runtime —
// changing `href` while leaving a stale `integrity` would make the
// browser refuse the new stylesheet and break the UI (issue #19).
// Hashes verified against cdnjs's SRI API. The corresponding static
// tag in static/index.html carries crossorigin="anonymous" which
// persists across runtime href swaps.
export const HLJS_THEME_SHEETS = {
    dark:  {
        href:      'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/vs2015.min.css',
        integrity: 'sha512-mtXspRdOWHCYp+f4c7CkWGYPPRAhq9X+xCvJMUBVAb6pqA4U8pxhT3RWT3LP3bKbiolYL2CkL1bSKZZO4eeTew==',
    },
    light: {
        href:      'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css',
        integrity: 'sha512-0aPQyyeZrWj9sCA46UlmWgKOP0mUipLQ6OZXu8l4IcAmD2u31EPEy9VcIMvl7SoAaKe8bLXZhYoMaE/in+gcgA==',
    },
};

export function applyHljsTheme(themeName) {
    const link = document.getElementById('hljs-theme');
    if (!link) return;
    const sheet = HLJS_THEME_SHEETS[themeName] || HLJS_THEME_SHEETS.dark;
    // Set integrity FIRST, then href — the browser reads the current
    // integrity at fetch time, and href change is what triggers the fetch.
    link.integrity = sheet.integrity;
    link.href = sheet.href;
}

export function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    const moon = document.getElementById('icon-moon');
    const sun = document.getElementById('icon-sun');
    if (moon && sun) {
        moon.style.display = theme === 'dark' ? 'block' : 'none';
        sun.style.display = theme === 'light' ? 'block' : 'none';
    }
    applyHljsTheme(theme);  // href + integrity swapped together (issue #19)
}

export function toggleTheme() {
    const current = localStorage.getItem('theme') || 'dark';
    applyTheme(current === 'dark' ? 'light' : 'dark');
}

export function setWorkspaceMode(active) {
    document.body.classList.toggle('workspace-mode', active);
    // Switch highlight.js theme — helper updates href + integrity together (issue #19).
    applyHljsTheme(localStorage.getItem('theme') || 'dark');
}
