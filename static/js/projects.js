// Projects home page — project list rendering.

import { state } from './shared/state.js';
import { esc, formatDate, smoothSet, loadingBar, setHamburgerVisible } from './shared/utils.js';
import { setWorkspaceMode } from './shared/theme.js';

// ==================== Projects (home) ====================

export async function showProjects() {
    state.currentProject = null;
    setHamburgerVisible(false);
    setWorkspaceMode(false);
    if (window.location.hash && window.location.hash !== '#') {
        state.navInProgress = true;
        window.location.hash = '';
        setTimeout(() => { state.navInProgress = false; }, 0);
    }
    const content = document.getElementById('content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading projects...</p></div>';
    loadingBar.start();

    try {
        const [projRes, stateRes] = await Promise.all([
            fetch('/api/projects'),
            fetch('/api/export/state').catch(() => null),
        ]);
        const projects = await projRes.json();
        loadingBar.done();

        if (!projects.length) {
            smoothSet(content, '<div class="empty-state">No Claude Code projects found.<br>Make sure Claude Code has been used on this machine.</div>');
            return;
        }

        for (const p of projects) state.projectDisplayNames[p.name] = p.display_name || p.name;
        projects.sort((a, b) => (b.last_modified || '').localeCompare(a.last_modified || ''));

        let lastExportHtml = '';
        let hasPreviousExport = false;
        if (stateRes) {
            try {
                const exportState = await stateRes.json();
                if (exportState.last_export_time) {
                    const d = new Date(exportState.last_export_time);
                    if (!isNaN(d.getTime())) {
                        hasPreviousExport = true;
                        const sessionCount = exportState.last_export_session_count ?? exportState.export_count ?? 0;
                        lastExportHtml = `<p class="text-muted text-sm" style="margin:0">Last export: ${d.toLocaleString()} (${sessionCount} sessions in last export)</p>`;
                    }
                }
            } catch(e) {}
        }

        const sinceBtnHtml = hasPreviousExport
            ? `<button class="btn btn-primary btn-sm" id="btn-export-since" onclick="bulkExport('incremental')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Export new since last
              </button>`
            : '';

        let html = `<div class="page-header">
            <div>
                <h1>Projects</h1>
                <p class="text-muted">Browse your Claude Code conversations by project. Click on a project to view its sessions.</p>
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:0.4rem">
                <div class="btn-group">
                    ${sinceBtnHtml}
                    <button class="btn btn-outline btn-sm" id="btn-export-all" onclick="bulkExport('all')">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        Export all
                    </button>
                </div>
                ${lastExportHtml}
            </div>
        </div>`;

        const withSessions = projects.filter(p => (p.session_count || 0) > 0);
        const noSessions   = projects.filter(p => (p.session_count || 0) === 0);

        if (withSessions.length) {
            html += `<div class="card">
                <div class="card-header">
                    <h2 class="card-title">Projects with Sessions</h2>
                    <p class="text-muted text-sm">${withSessions.length} project${withSessions.length !== 1 ? 's' : ''} with chat history</p>
                </div>
                <div class="card-body" style="padding:0">
                    <table class="table">
                        <thead><tr><th>Project</th><th>Sessions</th><th>Last Modified</th></tr></thead>
                        <tbody>`;
            for (const p of withSessions) {
                const displayName = p.display_name || p.name;
                const count = p.session_count || 0;
                html += `<tr>
                    <td><a href="#project/${encodeURIComponent(p.name)}" class="link">${esc(displayName)}</a></td>
                    <td><span class="text-success">${count} session${count !== 1 ? 's' : ''}</span></td>
                    <td>${esc(p.last_modified ? formatDate(p.last_modified) : '')}</td>
                </tr>`;
            }
            html += `</tbody></table></div></div>`;
        }

        if (noSessions.length) {
            html += `<div class="card" style="margin-top:1.5rem">
                <div class="card-header">
                    <h2 class="card-title">Projects without Sessions</h2>
                    <p class="text-muted text-sm">${noSessions.length} project${noSessions.length !== 1 ? 's' : ''} with no sessions found</p>
                </div>
                <div class="card-body">
                    <div class="alert alert-info">These projects may have no recorded sessions yet.</div>
                    <table class="table">
                        <thead><tr><th>Project</th><th>Sessions</th><th>Last Modified</th></tr></thead>
                        <tbody>`;
            for (const p of noSessions) {
                html += `<tr>
                    <td><span class="text-muted">${esc(p.display_name || p.name)}</span></td>
                    <td><span class="text-muted">0</span></td>
                    <td>${esc(p.last_modified ? formatDate(p.last_modified) : '')}</td>
                </tr>`;
            }
            html += `</tbody></table></div></div>`;
        }

        smoothSet(content, html);
    } catch (e) {
        loadingBar.done();
        smoothSet(content, `<div class="loading"><p class="text-danger">Failed to load projects.</p></div>`);
    }
}
