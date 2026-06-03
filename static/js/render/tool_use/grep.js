import { esc } from '../../shared/utils.js';
import { getToolSummary } from './summary.js';
import { wrapToolUse } from './common.js';

export function renderGrepUse(tool) {
    const inp = tool.input || {};
    const summary = getToolSummary('Grep', inp);
    const body = `<div class="tool-call-section">Pattern: <code>${esc(inp.pattern || '')}</code>${inp.path ? ' in <code>' + esc(inp.path) + '</code>' : ''}</div>`;
    return wrapToolUse(summary, body);
}
