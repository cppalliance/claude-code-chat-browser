import { esc, truncate } from '../../shared/utils.js';
import { getToolSummary } from './summary.js';
import { wrapToolUse } from './common.js';

export function renderTaskUse(tool) {
    const inp = tool.input || {};
    const summary = getToolSummary('Task', inp);
    let body = `<div class="tool-call-section">${esc(inp.subagent_type || '')} &mdash; ${esc(inp.description || '')}</div>`;
    if (inp.prompt) body += `<div class="tool-call-section"><div class="tool-call-section-title">Prompt</div><pre><code>${esc(truncate(inp.prompt, 500))}</code></pre></div>`;
    return wrapToolUse(summary, body);
}
