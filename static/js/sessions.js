// Session workspace — sidebar, session loading, message rendering.

import { state } from './shared/state.js';
import { esc, truncate, formatDate, formatTs, smoothSet, loadingBar, showToast, closeSidebar, setHamburgerVisible } from './shared/utils.js';
import { renderMarkdown, cleanContent } from './shared/markdown.js';
import { setWorkspaceMode } from './shared/theme.js';
import { downloadSession } from './export.js';

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
            <a class="btn btn-ghost btn-sm back-link" href="#" onclick="showProjects();return false;">
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
                <button class="btn btn-outline btn-sm" onclick="copyAll()">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    Copy All
                </button>
                <button type="button" class="btn btn-outline btn-sm" data-download-project="${esc(projectName)}" data-download-session="${esc(sessionId)}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    Download
                </button>
            </div>`;
            bindWorkspaceDownloadClick(wsActions);
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
        if (_toolResultHasBody(msg.tool_result_parsed)) return renderToolResult(msg.tool_result_parsed);
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

function getToolSummary(name, inp) {
    if (name === 'Bash') return `Bash: ${truncate(inp.command || '', 80)}`;
    if (name === 'Read') return `Read: ${esc(inp.file_path || '')}`;
    if (name === 'Write') return `Write: ${esc(inp.file_path || '')}`;
    if (name === 'Edit') return `Edit: ${esc(inp.file_path || '')}`;
    if (name === 'Glob') return `Glob: ${esc(inp.pattern || '')}`;
    if (name === 'Grep') return `Grep: /${esc(inp.pattern || '')}/` + (inp.path ? ` in ${esc(inp.path)}` : '');
    if (name === 'WebFetch') return `Fetch: ${truncate(inp.url || '', 80)}`;
    if (name === 'WebSearch') return `Search: ${truncate(inp.query || '', 80)}`;
    if (name === 'Task') return `Task: ${esc(inp.subagent_type || '')} - ${esc(inp.description || '')}`;
    if (name === 'TodoWrite') return 'TodoWrite';
    if (name === 'AskUserQuestion') return 'AskUserQuestion';
    return name;
}

function renderToolUse(tool) {
    const name = tool.name || 'unknown';
    const inp = tool.input || {};
    const summary = getToolSummary(name, inp);

    let body = '';

    if (name === 'Bash') {
        body += `<div class="tool-call-section"><div class="tool-call-section-title">Command</div><pre><code>${esc(inp.command || '')}</code></pre></div>`;
        if (inp.description) body += `<div class="tool-call-section"><div class="tool-call-section-title">Description</div><div>${esc(inp.description)}</div></div>`;
    } else if (name === 'Read') {
        body += `<div class="tool-call-section">File: <code>${esc(inp.file_path || '')}</code></div>`;
    } else if (name === 'Write') {
        body += `<div class="tool-call-section">File: <code>${esc(inp.file_path || '')}</code></div>`;
        if (inp.content) body += `<div class="tool-call-section"><div class="tool-call-section-title">Content</div><pre><code>${esc(truncate(inp.content, 500))}</code></pre></div>`;
    } else if (name === 'Edit') {
        body += `<div class="tool-call-section">File: <code>${esc(inp.file_path || '')}</code></div>`;
        if (inp.old_string) body += `<div class="tool-call-section"><div class="tool-call-section-title">Old</div><pre style="border-left:3px solid var(--danger)"><code>${esc(truncate(inp.old_string, 300))}</code></pre></div>`;
        if (inp.new_string) body += `<div class="tool-call-section"><div class="tool-call-section-title">New</div><pre style="border-left:3px solid var(--success)"><code>${esc(truncate(inp.new_string, 300))}</code></pre></div>`;
    } else if (name === 'Glob') {
        body += `<div class="tool-call-section">Pattern: <code>${esc(inp.pattern || '')}</code>${inp.path ? ' in <code>' + esc(inp.path) + '</code>' : ''}</div>`;
    } else if (name === 'Grep') {
        body += `<div class="tool-call-section">Pattern: <code>${esc(inp.pattern || '')}</code>${inp.path ? ' in <code>' + esc(inp.path) + '</code>' : ''}</div>`;
    } else if (name === 'Task') {
        body += `<div class="tool-call-section">${esc(inp.subagent_type || '')} &mdash; ${esc(inp.description || '')}</div>`;
        if (inp.prompt) body += `<div class="tool-call-section"><div class="tool-call-section-title">Prompt</div><pre><code>${esc(truncate(inp.prompt, 500))}</code></pre></div>`;
    } else if (name === 'TodoWrite') {
        const todos = inp.todos || [];
        for (const t of todos) {
            const icon = {'completed': '[x]', 'in_progress': '[~]', 'pending': '[ ]'}[t.status] || '[ ]';
            body += `<div>${icon} ${esc(t.content || '')}</div>`;
        }
    } else if (name === 'AskUserQuestion') {
        const questions = inp.questions || [];
        for (const q of questions) {
            body += `<div class="tool-call-section"><strong>Q:</strong> ${esc(q.question || '')}</div>`;
        }
    } else {
        const s = JSON.stringify(inp, null, 2);
        body += `<pre><code>${esc(truncate(s, 500))}</code></pre>`;
    }

    return `<details class="tool-call"><summary class="tool-name">${esc(summary)}</summary><div class="tool-call-body">${body}</div></details>`;
}

function _toolResultHasBody(parsed) {
    const rt = parsed.result_type || 'unknown';
    if (rt === 'bash') return !!(parsed.stdout || parsed.stderr);
    if (rt === 'todo_write') return !!(parsed.todos && parsed.todos.length);
    if (rt === 'user_input') return true;
    if (rt === 'task' && (parsed.total_duration_ms || parsed.retrieval_status || parsed.description)) return true;
    return false;
}

function renderToolResult(parsed) {
    const rt = parsed.result_type || 'unknown';
    let summary = '';
    let body = '';

    if (rt === 'bash') {
        const exitCode = parsed.exit_code;
        const status = parsed.interrupted ? 'interrupted' : (parsed.is_error ? `error (exit ${exitCode})` : (exitCode === 0 ? 'success' : `exit ${exitCode}`));
        summary = `Bash Result (${status})`;
        if (parsed.stdout) body += `<div class="tool-call-section"><div class="tool-call-section-title">stdout</div><pre><code>${esc(truncate(parsed.stdout, 2000))}</code></pre></div>`;
        if (parsed.stderr) body += `<div class="tool-call-section"><div class="tool-call-section-title">stderr</div><pre style="border-left:3px solid var(--danger)"><code>${esc(truncate(parsed.stderr, 1000))}</code></pre></div>`;
    } else if (rt === 'file_read') {
        const numLines = parsed.num_lines ? ` (${parsed.num_lines} lines)` : '';
        summary = `Read: ${parsed.file_path || ''}${numLines}`;
    } else if (rt === 'file_edit') {
        summary = `Edited: ${parsed.file_path || ''}`;
    } else if (rt === 'file_write') {
        summary = `Wrote: ${parsed.file_path || ''}`;
    } else if (rt === 'glob') {
        const trunc = parsed.truncated ? ' (truncated)' : '';
        summary = `Glob: ${parsed.num_files || 0} files found${trunc}`;
    } else if (rt === 'grep') {
        summary = `Grep: ${parsed.num_files || 0} files, ${parsed.num_lines || 0} lines`;
    } else if (rt === 'web_search') {
        summary = `Search: "${parsed.query || ''}" - ${parsed.result_count || 0} results`;
    } else if (rt === 'web_fetch') {
        summary = `Fetch: ${parsed.url || ''} (${parsed.status_code || '?'})`;
    } else if (rt === 'task') {
        const status = parsed.status || 'completed';
        const dur = parsed.total_duration_ms;
        const durStr = dur ? ` (${(dur / 1000).toFixed(1)}s)` : '';
        const tokStr = parsed.total_tokens ? `, ${parsed.total_tokens.toLocaleString()} tokens` : '';
        const toolStr = parsed.total_tool_use_count ? `, ${parsed.total_tool_use_count} tool calls` : '';
        summary = `Task ${status}${durStr}${tokStr}${toolStr}`;
        if (parsed.retrieval_status) summary = `Task retrieval: ${parsed.retrieval_status}`;
        if (parsed.description) summary = `Task launched: ${parsed.description}`;
    } else if (rt === 'todo_write') {
        const count = parsed.todo_count || 0;
        summary = `Todos updated (${count} items)`;
        if (parsed.todos && parsed.todos.length) {
            for (const t of parsed.todos) {
                const icon = {'completed': '\u2705', 'in_progress': '\u23f3', 'pending': '\u2b1c'}[t.status] || '\u2b1c';
                body += `<div>${icon} ${esc(t.content || '')}</div>`;
            }
        }
    } else if (rt === 'user_input') {
        summary = 'User input received';
        const qs = parsed.questions || [];
        const ans = parsed.answers || {};
        for (const q of qs) {
            body += `<div class="tool-call-section"><strong>Q:</strong> ${esc(q.question || '')}</div>`;
        }
        const ansKeys = Object.keys(ans);
        if (ansKeys.length) {
            for (const k of ansKeys) {
                body += `<div class="tool-call-section"><strong>A:</strong> ${esc(String(ans[k]))}</div>`;
            }
        }
    } else if (rt === 'plan') {
        summary = `Plan: ${parsed.file_path || ''}`;
    } else {
        summary = `Tool result (${rt})`;
    }

    if (!body) {
        return `<div class="tool-result"><span class="tool-result-summary">${esc(summary)}</span></div>`;
    }
    return `<details class="tool-result"><summary class="tool-result-summary">${esc(summary)}</summary><div class="tool-call-body">${body}</div></details>`;
}

export function copyAll() {
    const sessionEl = document.querySelector('.session-content-inner') || document.querySelector('#session-content');
    if (!sessionEl) return;
    const text = sessionEl.innerText;
    navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard', 'success'));
}
