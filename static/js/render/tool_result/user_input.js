import { esc } from '../../shared/utils.js';
import { finishToolResult } from './common.js';

export function renderUserInputResult(parsed) {
    const summary = 'User input received';
    let body = '';
    const qs = parsed.questions || [];
    const ans = parsed.answers || {};
    for (const q of qs) {
        body += `<div class="tool-call-section"><strong>Q:</strong> ${esc(q.question || '')}</div>`;
    }
    const ansKeys = Object.keys(ans);
    if (ansKeys.length) {
        for (const k of ansKeys) {
            body += `<div class="tool-call-section"><strong>A:</strong> ${esc(String(ans[k]))}</div>`;
        }
    }
    return finishToolResult(summary, body);
}
