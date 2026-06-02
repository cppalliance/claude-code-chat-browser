import { esc, truncate } from '../../shared/utils.js';
import { getToolSummary } from './summary.js';
import { wrapToolUse } from './common.js';

export function renderEditUse(tool) {
    const inp = tool.input || {};
    const summary = getToolSummary('Edit', inp);
    let body = `<div class="tool-call-section">File: <code>${esc(inp.file_path || '')}</code></div>`;
    if (inp.old_string) body += `<div class="tool-call-section"><div class="tool-call-section-title">Old</div><pre style="border-left:3px solid var(--danger)"><code>${esc(truncate(inp.old_string, 300))}</code></pre></div>`;
    if (inp.new_string) body += `<div class="tool-call-section"><div class="tool-call-section-title">New</div><pre style="border-left:3px solid var(--success)"><code>${esc(truncate(inp.new_string, 300))}</code></pre></div>`;
    return wrapToolUse(summary, body);
}
