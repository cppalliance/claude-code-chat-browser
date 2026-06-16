// Search page — search UI and result rendering.

import { esc, smoothSet, setHamburgerVisible } from './shared/utils.js';
import { setWorkspaceMode } from './shared/theme.js';
import { showProjects } from './projects.js';

// ==================== Search ====================

let lastSearchRequestId = 0;

export function showSearchPage() {
    setHamburgerVisible(false);
    setWorkspaceMode(false);
    window.location.hash = '#search';
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="search-page">
            <a class="back-link" href="#" id="search-back-link">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
                Back to Projects
            </a>
            <br><br>
            <h1>Search</h1>
            <div class="search-bar">
                <input class="input" type="text" id="search-input" placeholder="Search conversations..." autofocus>
                <button type="button" class="btn btn-primary" id="search-submit-btn">Search</button>
            </div>
            <div id="search-results"></div>
        </div>`;
    document.getElementById('search-back-link')?.addEventListener('click', (e) => {
        e.preventDefault();
        showProjects();
    });
    document.getElementById('search-submit-btn')?.addEventListener('click', doSearch);
    document.getElementById('search-input')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') doSearch();
    });
    document.getElementById('search-results').addEventListener('click', (e) => {
        if (!(e.target instanceof Element)) return;
        const result = e.target.closest('.search-result[data-project]');
        if (!result) return;
        const project = result.getAttribute('data-project');
        const sessionId = result.getAttribute('data-session-id');
        if (!project || !sessionId) return;
        window.location.hash = `#project/${encodeURIComponent(project)}/${encodeURIComponent(sessionId)}`;
    });
    document.getElementById('search-input').focus();
}

export async function doSearch() {
    const localRequestId = ++lastSearchRequestId;
    const input = document.getElementById('search-input');
    if (!input) { showSearchPage(); return; }
    const query = input.value.trim();
    if (!query) return;

    const container = document.getElementById('search-results');
    container.innerHTML = '<div class="loading">Searching...</div>';

    try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=50`);
        if (localRequestId !== lastSearchRequestId) return;
        if (!res.ok) {
            let msg = `Search failed (${res.status})`;
            try { msg = await res.text() || msg; } catch { /* ignore */ }
            if (localRequestId !== lastSearchRequestId) return;
            throw new Error(msg);
        }
        const results = await res.json();
        if (localRequestId !== lastSearchRequestId) return;

        let html = `<p class="text-muted text-sm">${results.length} result${results.length !== 1 ? 's' : ''}</p><br>`;
        html += '<div class="search-results">';

        for (const r of results) {
            html += `<div class="search-result" data-project="${esc(r.project)}" data-session-id="${esc(r.session_id)}">
                <div><strong>${esc(r.title)}</strong> <span class="text-muted text-sm">${esc(r.project)} &bull; ${esc(r.role)}</span></div>
                <div class="snippet">...${esc(r.snippet)}...</div>
            </div>`;
        }

        if (!results.length) html += '<div class="empty-state">No results found.</div>';
        html += '</div>';
        smoothSet(container, html);
    } catch (e) {
        if (localRequestId !== lastSearchRequestId) return;
        container.innerHTML = `<div class="loading">Error: ${esc(e.message)}</div>`;
    }
}
