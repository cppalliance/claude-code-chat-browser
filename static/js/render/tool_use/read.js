import { esc } from '../../shared/utils.js';
import { getToolSummary } from './summary.js';
import { wrapToolUse } from './common.js';

export function renderReadUse(tool) {
    const inp = tool.input || {};
    const summary = getToolSummary('Read', inp);
    const body = `<div class="tool-call-section">File: <code>${esc(inp.file_path || '')}</code></div>`;
    return wrapToolUse(summary, body);
}
