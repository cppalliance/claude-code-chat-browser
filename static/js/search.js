// Search page — search UI and result rendering.

import { esc, smoothSet } from './shared/utils.js';
import { setHamburgerVisible, setWorkspaceMode } from './shared/theme.js';

// ==================== Search ====================

export function showSearchPage() {
    setHamburgerVisible(false);
    setWorkspaceMode(false);
    window.location.hash = '#search';
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="search-page">
            <a class="back-link" href="#" onclick="showProjects();return false;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
                Back to Projects
            </a>
            <br><br>
            <h1>Search</h1>
            <div class="search-bar">
                <input class="input" type="text" id="search-input" placeholder="Search conversations..." autofocus
                       onkeydown="if(event.key==='Enter') doSearch()">
                <button class="btn btn-primary" onclick="doSearch()">Search</button>
            </div>
            <div id="search-results"></div>
        </div>`;
    document.getElementById('search-input').focus();
}

export async function doSearch() {
    const input = document.getElementById('search-input');
    if (!input) { showSearchPage(); return; }
    const query = input.value.trim();
    if (!query) return;

    const container = document.getElementById('search-results');
    container.innerHTML = '<div class="loading">Searching...</div>';

    try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&limit=50`);
        const results = await res.json();

        let html = `<p class="text-muted text-sm">${results.length} result${results.length !== 1 ? 's' : ''}</p><br>`;
        html += '<div class="search-results">';

        for (const r of results) {
            html += `<div class="search-result" onclick="window.location.hash='#project/${encodeURIComponent(r.project)}/${r.session_id}'">
                <div><strong>${esc(r.title)}</strong> <span class="text-muted text-sm">${esc(r.project)} &bull; ${esc(r.role)}</span></div>
                <div class="snippet">...${esc(r.snippet)}...</div>
            </div>`;
        }

        if (!results.length) html += '<div class="empty-state">No results found.</div>';
        html += '</div>';
        smoothSet(container, html);
    } catch (e) {
        container.innerHTML = `<div class="loading">Error: ${esc(e.message)}</div>`;
    }
}
