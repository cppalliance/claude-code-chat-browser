import { esc, truncate } from '../../shared/utils.js';
import { wrapToolUse } from './common.js';
import { UNKNOWN_DISPATCH_KEY } from '../constants.js';

export function renderToolUseFallback(tool) {
    const name = tool.name || UNKNOWN_DISPATCH_KEY;
    const inp = tool.input || {};
    const summary = `Unknown tool: ${name}`;
    const s = JSON.stringify(inp, null, 2);
    const body = `<pre><code>${esc(truncate(s, 500))}</code></pre>`;
    return wrapToolUse(summary, body);
}
