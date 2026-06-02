import { esc, truncate } from '../../shared/utils.js';
import { finishToolResult } from './common.js';

export function renderBashResult(parsed) {
    const exitCode = parsed.exit_code;
    let status;
    if (parsed.interrupted) {
        status = 'interrupted';
    } else if (parsed.is_error) {
        status = typeof exitCode === 'number' ? `error (exit ${exitCode})` : 'error';
    } else if (exitCode === 0) {
        status = 'success';
    } else if (typeof exitCode === 'number') {
        status = `exit ${exitCode}`;
    } else {
        status = 'unknown';
    }
    const summary = `Bash Result (${status})`;
    let body = '';
    if (parsed.stdout) body += `<div class="tool-call-section"><div class="tool-call-section-title">stdout</div><pre><code>${esc(truncate(parsed.stdout, 2000))}</code></pre></div>`;
    if (parsed.stderr) body += `<div class="tool-call-section"><div class="tool-call-section-title">stderr</div><pre style="border-left:3px solid var(--danger)"><code>${esc(truncate(parsed.stderr, 1000))}</code></pre></div>`;
    return finishToolResult(summary, body);
}
