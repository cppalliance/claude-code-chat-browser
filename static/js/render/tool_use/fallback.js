import { esc, truncate } from '../../shared/utils.js';
import { getToolSummary } from './summary.js';
import { wrapToolUse } from './common.js';

export function renderToolUseFallback(tool) {
    const name = tool.name || 'unknown';
    const inp = tool.input || {};
    const summary = getToolSummary(name, inp);
    const s = JSON.stringify(inp, null, 2);
    const body = `<pre><code>${esc(truncate(s, 500))}</code></pre>`;
    return wrapToolUse(summary, body);
}
