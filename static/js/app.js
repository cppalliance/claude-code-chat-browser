// Claude Code Chat Browser — Entry module (router + theme + navbar wiring).
// Route modules live in sessions.js, projects.js, search.js, export.js.
// Shared helpers live in shared/utils.js, shared/markdown.js, shared/theme.js.

import { state } from './shared/state.js';
import { toggleSidebar, closeSidebar } from './shared/utils.js';
import { HLJS_THEME_SHEETS, applyTheme, toggleTheme } from './shared/theme.js';
import { showProjects } from './projects.js';
import { showWorkspace, loadSession } from './sessions.js';
import { showSearchPage } from './search.js';
import { initToolTypesManifest } from './render/tool_types_manifest.js';

// ==================== Router ====================

function safeDecode(str) {
    try { return decodeURIComponent(str); } catch { return null; }
}

function handleRoute() {
    if (state.navInProgress) return;
    window.scrollTo(0, 0);
    const hash = window.location.hash || '#';
    if (hash.startsWith('#project/')) {
        const parts = hash.slice(9);
        const slashIdx = parts.indexOf('/');
        if (slashIdx > 0) {
            const project = safeDecode(parts.slice(0, slashIdx));
            if (!project) { showProjects(); return; }
            const sessionId = parts.slice(slashIdx + 1);
            if (state.currentProject === project && state.cachedSessions.length > 0 && document.getElementById('sidebar')) {
                document.querySelectorAll('.sidebar-item').forEach(el => el.classList.remove('active'));
                const el = document.getElementById(`sidebar-${sessionId}`);
                if (el) { el.classList.add('active'); el.scrollIntoView({ block: 'nearest' }); }
                loadSession(project, sessionId);
            } else {
                showWorkspace(project, sessionId);
            }
        } else {
            const project = safeDecode(parts);
            if (!project) { showProjects(); return; }
            showWorkspace(project);
        }
    } else if (hash === '#search') {
        showSearchPage();
    } else {
        showProjects();
    }
}

// ==================== Bootstrap ====================

document.addEventListener('DOMContentLoaded', () => {
    applyTheme(localStorage.getItem('theme') || 'dark');
    const yearEl = document.getElementById('footer-year');
    if (yearEl) yearEl.textContent = new Date().getFullYear();
    void initToolTypesManifest();
    handleRoute();
    window.addEventListener('hashchange', handleRoute);

    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    overlay.id = 'sidebar-overlay';
    overlay.addEventListener('click', closeSidebar);
    document.body.appendChild(overlay);

    const topBtn = document.createElement('button');
    topBtn.className = 'scroll-top-btn';
    topBtn.id = 'scroll-top-btn';
    topBtn.textContent = '\u2191';
    topBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    document.body.appendChild(topBtn);
    window.addEventListener('scroll', () => topBtn.classList.toggle('show', window.scrollY > 400));

    document.getElementById('hamburger-btn')?.addEventListener('click', toggleSidebar);
    document.getElementById('navbar-brand')?.addEventListener('click', (e) => {
        e.preventDefault();
        showProjects();
    });
    document.getElementById('nav-search-link')?.addEventListener('click', (e) => {
        e.preventDefault();
        showSearchPage();
    });
    document.getElementById('theme-toggle')?.addEventListener('click', toggleTheme);
});

// Keep HLJS_THEME_SHEETS accessible for test_hljs_theme_consistency.py (source-level check)
export { HLJS_THEME_SHEETS };
