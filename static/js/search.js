// Search page — search UI and result rendering.

import { esc, smoothSet, setHamburgerVisible } from './shared/utils.js';
import { setWorkspaceMode } from './shared/theme.js';
import { showProjects } from './projects.js';

// ==================== Search ====================

const SEARCH_LIMIT = 50;

let lastSearchRequestId = 0;

export function highlightSnippet(snippet, query) {
    if (!snippet) return '';
    if (!query) return esc(snippet);
    const chars = [...snippet];
    const needle = [...query].map((ch) => ch.toLowerCase());
    const hay = chars.map((ch) => ch.toLowerCase());
    for (let i = 0; i <= hay.length - needle.length; i += 1) {
        let matched = true;
        for (let j = 0; j < needle.length; j += 1) {
            if (hay[i + j] !== needle[j]) {
                matched = false;
                break;
            }
        }
        if (!matched) continue;
        const before = chars.slice(0, i).join('');
        const match = chars.slice(i, i + needle.length).join('');
        const after = chars.slice(i + needle.length).join('');
        return esc(before) + '<mark>' + esc(match) + '</mark>' + esc(after);
    }
    return esc(snippet);
}

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
            <p class="text-muted text-sm search-help">
                By default, search covers the last 30 days. Chats without a parseable date may still appear.
                Results are capped at ${SEARCH_LIMIT} (up to 500 via the API). Check
                <label class="search-all-history-label">
                    <input type="checkbox" id="search-all-history"> Search all history
                </label>
                to include older messages.
            </p>
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
    document.getElementById('search-input')?.focus();
}

export async function doSearch() {
    const localRequestId = ++lastSearchRequestId;
    const input = document.getElementById('search-input');
    if (!input) { showSearchPage(); return; }
    const container = document.getElementById('search-results');
    const query = input.value.trim();
    if (!query) {
        container.innerHTML = '<p class="search-error">Enter a search term.</p>';
        return;
    }

    const allHistory = document.getElementById('search-all-history')?.checked;
    container.innerHTML = '<div class="search-loading">Searching...</div>';

    const params = new URLSearchParams({
        q: query,
        limit: String(SEARCH_LIMIT),
    });
    if (allHistory) params.set('all_history', '1');

    try {
        const res = await fetch(`/api/search?${params.toString()}`);
        if (localRequestId !== lastSearchRequestId) return;
        if (!res.ok) {
            let message = `Search failed (${res.status})`;
            let code = '';
            try {
                const body = await res.json();
                if (body && typeof body.error === 'string') message = body.error;
                if (body && typeof body.code === 'string') code = body.code;
            } catch {
                try { message = await res.text() || message; } catch { /* ignore */ }
            }
            if (localRequestId !== lastSearchRequestId) return;
            const codeAttr = code ? ` data-error-code="${esc(code)}"` : '';
            container.innerHTML = `<p class="search-error"${codeAttr}>${esc(message)}</p>`;
            return;
        }
        const results = await res.json();
        if (localRequestId !== lastSearchRequestId) return;

        let html = `<p class="text-muted text-sm">${results.length} result${results.length !== 1 ? 's' : ''}</p>`;
        if (results.length >= SEARCH_LIMIT) {
            html += `<p class="text-muted text-sm search-truncation">Showing the first ${SEARCH_LIMIT} matches. Narrow your query or raise <code>limit</code> in the API for more.</p>`;
        }
        html += '<div class="search-results">';

        for (const r of results) {
            html += `<div class="search-result" data-project="${esc(r.project)}" data-session-id="${esc(r.session_id)}">
                <div><strong>${esc(r.title)}</strong> <span class="text-muted text-sm">${esc(r.project)} &bull; ${esc(r.role)}</span></div>
                <div class="snippet">...${highlightSnippet(r.snippet, query)}...</div>
            </div>`;
        }

        if (!results.length) {
            html += '<div class="search-empty">No results found.</div>';
        }
        html += '</div>';
        smoothSet(container, html);
    } catch (e) {
        if (localRequestId !== lastSearchRequestId) return;
        container.innerHTML = `<p class="search-error">${esc(e.message)}</p>`;
    }
}
