import { esc, truncate } from '../../shared/utils.js';
import { getToolSummary } from './summary.js';
import { wrapToolUse } from './common.js';

export function renderWriteUse(tool) {
    const inp = tool.input || {};
    const summary = getToolSummary('Write', inp);
    let body = `<div class="tool-call-section">File: <code>${esc(inp.file_path || '')}</code></div>`;
    if (inp.content) body += `<div class="tool-call-section"><div class="tool-call-section-title">Content</div><pre><code>${esc(truncate(inp.content, 500))}</code></pre></div>`;
    return wrapToolUse(summary, body);
}
