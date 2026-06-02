import { esc } from '../../shared/utils.js';

export function finishToolResult(summary, body) {
    if (!body) {
        return `<div class="tool-result"><span class="tool-result-summary">${esc(summary)}</span></div>`;
    }
    return `<details class="tool-result"><summary class="tool-result-summary">${esc(summary)}</summary><div class="tool-call-body">${body}</div></details>`;
}
