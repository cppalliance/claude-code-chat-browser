import { esc } from '../../shared/utils.js';

export function wrapToolUse(summary, body) {
    return `<details class="tool-call"><summary class="tool-name">${esc(summary)}</summary><div class="tool-call-body">${body}</div></details>`;
}
