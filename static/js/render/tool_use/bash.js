import { esc } from '../../shared/utils.js';
import { getToolSummary } from './summary.js';
import { wrapToolUse } from './common.js';

export function renderBashUse(tool) {
    const inp = tool.input || {};
    const summary = getToolSummary('Bash', inp);
    let body = '';
    body += `<div class="tool-call-section"><div class="tool-call-section-title">Command</div><pre><code>${esc(inp.command || '')}</code></pre></div>`;
    if (inp.description) body += `<div class="tool-call-section"><div class="tool-call-section-title">Description</div><div>${esc(inp.description)}</div></div>`;
    return wrapToolUse(summary, body);
}
