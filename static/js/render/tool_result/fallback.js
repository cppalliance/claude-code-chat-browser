import { esc, truncate } from '../../shared/utils.js';
import { finishToolResult } from './common.js';
import { UNKNOWN_DISPATCH_KEY } from '../constants.js';

export function renderToolResultFallback(parsed) {
    const rt = parsed.result_type || UNKNOWN_DISPATCH_KEY;
    const summary = `Unknown tool result: ${rt}`;
    const payload = JSON.stringify(parsed, null, 2);
    const body = `<pre><code>${esc(truncate(payload, 500))}</code></pre>`;
    return finishToolResult(summary, body);
}
