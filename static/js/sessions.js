// Session workspace — sidebar, session loading, message rendering.

import { state } from './shared/state.js';
import { esc, formatDate, formatTs, smoothSet, loadingBar, showToast, closeSidebar, setHamburgerVisible } from './shared/utils.js';
import { renderMarkdown, cleanContent } from './shared/markdown.js';
import { setWorkspaceMode } from './shared/theme.js';
import { downloadSession } from './export.js';
import { showProjects } from './projects.js';
import { renderToolUse, renderToolResult, toolResultHasBody } from './render/registry.js';

// ==================== Schema drift banner ====================

const SCHEMA_DRIFT_DISMISS_KEY = 'schema-drift-banner-dismissed';

function schemaDriftFingerprint(report) {
    const parts = [
        ...(report.new_fields || []),
        ...(report.missing_fields || []),
    ].sort();
    return parts.join('|');
}

async function fetchSchemaDriftBannerHtml() {
    try {
        const res = await fetch('/api/schema-report');
        if (!res.ok) return '';
        const report = await res.json();
        if (!report.has_drift) return '';

        const fingerprint = schemaDriftFingerprint(report);
        if (sessionStorage.getItem(SCHEMA_DRIFT_DISMISS_KEY) === fingerprint) return '';

        const newFields = (report.new_fields || []).slice(0, 5);
        const missingFields = (report.missing_fields || []).slice(0, 5);
        let detail = '';
        if (newFields.length) {
            detail += `<div class="text-sm" style="margin-top:0.35rem">New fields: ${esc(newFields.join(', '))}${(report.new_fields || []).length > 5 ? '…' : ''}</div>`;
        }
        if (missingFields.length) {
            detail += `<div class="text-sm" style="margin-top:0.35rem">Missing required fields: ${esc(missingFields.join(', '))}${(report.missing_fields || []).length > 5 ? '…' : ''}</div>`;
        }

        return `<div class="alert alert-warning" id="schema-drift-banner" data-drift-fingerprint="${esc(fingerprint)}">
            <div class="alert-warning__body">
                <strong>Upstream JSONL schema drift detected</strong>
                <div class="text-sm" style="margin-top:0.25rem">Claude Code may have changed its session format. Parsing continues, but some data may be incomplete.</div>
                ${detail}
            </div>
            <button type="button" class="alert-warning__dismiss" id="schema-drift-dismiss" aria-label="Dismiss">×</button>
        </div>`;
    } catch {
        return '';
    }
}

function bindSchemaDriftBanner(root) {
    const banner = root.querySelector('#schema-drift-banner');
    const dismiss = root.querySelector('#schema-drift-dismiss');
    if (!banner || !dismiss) return;
    dismiss.addEventListener('click', () => {
        const fingerprint = banner.getAttribute('data-drift-fingerprint') || '';
        sessionStorage.setItem(SCHEMA_DRIFT_DISMISS_KEY, fingerprint);
        banner.remove();
    });
}

// ==================== Workspace (split layout) ====================

export async function showWorkspace(projectName, selectedSessionId) {
    state.currentProject = projectName;
    setHamburgerVisible(true);
    setWorkspaceMode(true);
    const content = document.getElementById('content');
    content.innerHTML = '<div style="padding:2rem"><div class="loading"><div class="spinner"></div><p>Loading sessions...</p></div></div>';
    loadingBar.start();

    try {
        if (!state.projectDisplayNames[projectName]) {
            const projRes = await fetch('/api/projects');
            const projects = await projRes.json();
            for (const p of projects) state.projectDisplayNames[p.name] = p.display_name || p.name;
        }
        const prettyName = state.projectDisplayNames[projectName] || projectName;

        const schemaBannerPromise = fetchSchemaDriftBannerHtml();
        const res = await fetch(`/api/projects/${encodeURIComponent(projectName)}/sessions`);
        state.cachedSessions = await res.json();

        state.cachedSessions.sort((a, b) => {
            const ta = a.last_timestamp || a.first_timestamp || '';
            const tb = b.last_timestamp || b.first_timestamp || '';
            return tb.localeCompare(ta);
        });

        const byDate = {};
        for (const s of state.cachedSessions) {
            const ts = s.last_timestamp || s.first_timestamp || '';
            const date = ts ? formatDate(ts) : 'Unknown';
            if (!byDate[date]) byDate[date] = [];
            byDate[date].push(s);
        }

        let sidebar = `<h3 style="margin-bottom:0.5rem;padding:0 0.25rem">Conversations <span class="text-sm text-muted" style="font-weight:400">(${state.cachedSessions.length})</span></h3>`;
        sidebar += '<div>';

        const dates = Object.keys(byDate).sort().reverse();
        for (const date of dates) {
            sidebar += `<div class="date-label">${esc(date)}</div>`;
            for (const s of byDate[date]) {
                const title = s.title || s.id;
                const ts = formatDate(s.last_timestamp || s.first_timestamp || '');
                const models = (s.models || []).join(', ');
                const isActive = s.id === selectedSessionId ? ' active' : '';
                const errorClass = s.error ? ' sidebar-item-error' : '';
                const errorDetail = s.error_detail ? `<div class="error-detail">${esc(s.error_detail)}</div>` : '';
                const modelBadge = models ? `<span style="font-size:0.65rem;opacity:0.6;display:block;margin-top:1px">${esc(models)}</span>` : '';
                sidebar += `<button type="button" class="sidebar-item${isActive}${errorClass}" data-project="${esc(projectName)}" data-session-id="${esc(s.id)}" id="sidebar-${esc(s.id)}">
                    <div class="sidebar-item-title">${esc(title)}</div>
                    ${errorDetail}
                    <div class="sidebar-item-time">${esc(ts)}${modelBadge}</div>
                </button>`;
            }
        }
        sidebar += '</div>';

        let html = `<div class="workspace-top-bar">
            <a class="btn btn-ghost btn-sm back-link" href="#" id="ws-back-link">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
                Back to Projects
            </a>
            <div id="ws-actions" class="btn-group"></div>
        </div>
        <div class="project-info card">
            <h2>${esc(prettyName)}</h2>
            <p class="text-sm text-muted">${state.cachedSessions.length} session${state.cachedSessions.length !== 1 ? 's' : ''}</p>
        </div>
        <div class="workspace-wrap">
            <div class="sidebar" id="sidebar">${sidebar}</div>
            <div class="main-panel" id="main-panel">
                <div id="session-content"><div class="card" style="padding:2rem;text-align:center"><p class="text-muted">No session selected</p></div></div>
            </div>
        </div>`;
        smoothSet(content, html);
        bindSidebarSessionClicks();
        void schemaBannerPromise.then((schemaBannerHtml) => {
            if (!schemaBannerHtml) return;
            const root = document.getElementById('content');
            if (!root) return;
            root.insertAdjacentHTML('afterbegin', schemaBannerHtml);
            bindSchemaDriftBanner(root);
        });
        content.querySelector('#ws-back-link')?.addEventListener('click', (e) => {
            e.preventDefault();
            showProjects();
        });
        loadingBar.done();

        if (selectedSessionId) {
            loadSession(projectName, selectedSessionId);
        } else if (state.cachedSessions.length > 0) {
            selectSession(projectName, state.cachedSessions[0].id);
        }
    } catch (e) {
        loadingBar.done();
        content.innerHTML = `<div class="loading">Error: ${esc(e.message)}</div>`;
    }
}

function bindSidebarSessionClicks() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    sidebar.addEventListener('click', (e) => {
        if (!(e.target instanceof Element)) return;
        const btn = e.target.closest('button.sidebar-item[data-session-id]');
        if (!btn) return;
        const project = btn.getAttribute('data-project');
        const sessionId = btn.getAttribute('data-session-id');
        if (!project || !sessionId) return;
        selectSession(project, sessionId);
    });
}

function bindWorkspaceDownloadClick(wsActions) {
    const btn = wsActions.querySelector('[data-download-session]');
    if (!btn) return;
    btn.addEventListener('click', () => {
        const project = btn.getAttribute('data-download-project');
        const sessionId = btn.getAttribute('data-download-session');
        if (project == null || sessionId == null) return;
        downloadSession(project, sessionId);
    });
}

export function selectSession(projectName, sessionId) {
    closeSidebar();
    window.location.hash = `#project/${encodeURIComponent(projectName)}/${encodeURIComponent(sessionId)}`;
}

export async function loadSession(projectName, sessionId) {
    const container = document.getElementById('session-content');
    if (!container) return;
    loadingBar.start();

    try {
        const res = await fetch(`/api/sessions/${encodeURIComponent(projectName)}/${encodeURIComponent(sessionId)}`);
        if (!res.ok) {
            loadingBar.done();
            const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
            container.innerHTML = `<div class="loading">Error loading session: ${esc(err.error || res.statusText)}</div>`;
            return;
        }
        const session = await res.json();
        if (session.error) {
            loadingBar.done();
            container.innerHTML = `<div class="loading">Error: ${esc(session.error)}</div>`;
            return;
        }
        const meta = session.metadata;

        let html = '';

        const modelsList = (meta.models_used || []).filter(m => m !== '<synthetic>');
        const totalTokens = (meta.total_input_tokens + meta.total_output_tokens).toLocaleString();
        const msgCount = session.messages.filter(m => m.role === 'user' && m.text && m.text.trim()).length;

        let subtitleParts = [];
        if (meta.first_timestamp) subtitleParts.push(formatTs(meta.first_timestamp));
        if (meta.last_timestamp && meta.last_timestamp !== meta.first_timestamp) subtitleParts.push(formatTs(meta.last_timestamp));
        const timeRange = subtitleParts.length === 2
            ? `${subtitleParts[0]} &rarr; ${subtitleParts[1]}`
            : subtitleParts[0] || '';

        let badges = '';
        if (modelsList.length === 0) badges += `<span class="stat-badge badge-model">N/A</span>`;
        else modelsList.forEach(m => { badges += `<span class="stat-badge badge-model">${esc(m)}</span>`; });
        badges += `<span class="stat-badge badge-tokens">${totalTokens} tokens</span>`;
        badges += `<span class="stat-badge badge-tools">${meta.total_tool_calls} tool calls</span>`;
        if (meta.compactions > 0) badges += `<span class="stat-badge badge-compact">${meta.compactions} compaction${meta.compactions > 1 ? 's' : ''}</span>`;
        if (meta.cwd) badges += `<span class="stat-badge badge-dir" title="${esc(meta.cwd)}">${esc(meta.cwd)}</span>`;
        if (meta.git_branch) badges += `<span class="stat-badge badge-branch">${esc(meta.git_branch)}</span>`;
        if (meta.version) badges += `<span class="stat-badge badge-version">v${esc(meta.version)}</span>`;
        if (meta.permission_mode) badges += `<span class="stat-badge badge-perm">${esc(meta.permission_mode)}</span>`;

        const wsActions = document.getElementById('ws-actions');
        if (wsActions) {
            wsActions.innerHTML = `<div class="btn-group">
                <button type="button" class="btn btn-outline btn-sm" id="btn-copy-all">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    Copy All
                </button>
                <button type="button" class="btn btn-outline btn-sm" data-download-project="${esc(projectName)}" data-download-session="${esc(sessionId)}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    Download
                </button>
            </div>`;
            bindWorkspaceDownloadClick(wsActions);
            wsActions.querySelector('#btn-copy-all')?.addEventListener('click', copyAll);
        }

        html += `<div class="card">
        <div class="panel-header">
            <div class="panel-header-left">
                <h2 class="panel-title">${esc(session.title)}</h2>
                <div class="panel-subtitle">
                    <span class="panel-time">${timeRange}</span>
                    <span class="panel-msg-count">${msgCount} message${msgCount !== 1 ? 's' : ''}</span>
                </div>
                <div class="stat-badges">${badges}</div>
            </div>
        </div>`;

        html += '<div class="chat-bubbles">';
        for (const msg of session.messages) {
            if (msg.role === 'user') html += renderUser(msg);
            else if (msg.role === 'assistant') html += renderAssistant(msg);
            else if (msg.role === 'system') html += renderSystem(msg);
        }
        html += '</div></div>';

        smoothSet(container, `<div class="session-content-inner">${html}</div>`);
        loadingBar.done();

        container.querySelectorAll('pre code').forEach(block => {
            if (typeof hljs !== 'undefined') hljs.highlightElement(block);
        });
    } catch (e) {
        loadingBar.done();
        container.innerHTML = `<div class="chat-bubbles"><div class="bubble bubble-system">Error: ${esc(e.message)}</div></div>`;
    }
}

// ==================== Message renderers ====================

function renderUser(msg) {
    const hasText = msg.text && msg.text.trim();
    const hasImages = msg.images && msg.images.length > 0;
    const hasToolResult = msg.tool_result_parsed;

    if (!hasText && !hasImages && !hasToolResult) return '';

    if (hasToolResult && !hasText && !hasImages) {
        if (toolResultHasBody(msg.tool_result_parsed)) return renderToolResult(msg.tool_result_parsed);
        return '';
    }

    let html = `<div class="bubble bubble-user">`;
    html += `<div class="bubble-header"><span class="badge">You</span><span class="text-sm text-muted">${msg.timestamp ? formatDate(msg.timestamp) : ''}</span></div>`;
    if (hasImages) {
        for (const img of msg.images) {
            html += `<div class="msg-image"><img src="data:${esc(img.media_type)};base64,${img.data}" alt="User image" loading="lazy"></div>`;
        }
    }
    if (hasText) html += `<div class="bubble-text prose">${renderMarkdown(cleanContent(msg.text))}</div>`;
    if (hasToolResult) html += renderToolResult(msg.tool_result_parsed);
    html += '</div>';
    return html;
}

function renderAssistant(msg) {
    const hasText = msg.text && msg.text.trim();
    const hasThinking = msg.thinking && msg.thinking.trim();
    const hasTools = msg.tool_uses && msg.tool_uses.length > 0;
    if (!hasText && !hasThinking && !hasTools) return '';

    let html = `<div class="bubble bubble-ai">`;
    html += `<div class="bubble-header"><span class="badge badge-secondary">AI</span><span class="text-sm text-muted">${msg.timestamp ? formatDate(msg.timestamp) : ''}</span></div>`;

    let metaParts = [];
    if (msg.model && msg.model !== '<synthetic>') metaParts.push(esc(msg.model));
    if (msg.usage && msg.usage.output_tokens) metaParts.push(`${msg.usage.output_tokens.toLocaleString()} tokens`);
    if (metaParts.length) html += `<div class="bubble-meta">${metaParts.join(' &bull; ')}</div>`;

    if (hasThinking) {
        html += `<details class="thinking-block"><summary>Thinking</summary><div class="thinking-content">${esc(msg.thinking)}</div></details>`;
    }
    if (hasText) html += `<div class="bubble-text prose">${renderMarkdown(cleanContent(msg.text))}</div>`;
    if (hasTools) {
        for (const tool of msg.tool_uses) html += renderToolUse(tool);
    }
    html += '</div>';
    return html;
}

function renderSystem(msg) {
    if (msg.subtype === 'compact_boundary') {
        return '<div class="bubble bubble-system"><em>--- Context compacted ---</em></div>';
    }
    if (msg.content) {
        return `<div class="bubble bubble-system">${esc(msg.content)}</div>`;
    }
    return '';
}

export function copyAll() {
    const sessionEl = document.querySelector('.session-content-inner') || document.querySelector('#session-content');
    if (!sessionEl) return;
    const text = sessionEl.innerText;
    navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard', 'success'));
}
