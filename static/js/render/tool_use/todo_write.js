import { esc } from '../../shared/utils.js';
import { getToolSummary } from './summary.js';
import { wrapToolUse } from './common.js';

export function renderTodoWriteUse(tool) {
    const inp = tool.input || {};
    const summary = getToolSummary('TodoWrite', inp);
    let body = '';
    const todos = inp.todos || [];
    for (const t of todos) {
        const icon = {'completed': '[x]', 'in_progress': '[~]', 'pending': '[ ]'}[t.status] || '[ ]';
        body += `<div>${icon} ${esc(t.content || '')}</div>`;
    }
    return wrapToolUse(summary, body);
}
