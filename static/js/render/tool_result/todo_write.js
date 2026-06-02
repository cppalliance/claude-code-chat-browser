import { esc } from '../../shared/utils.js';
import { finishToolResult } from './common.js';

export function renderTodoWriteResult(parsed) {
    const count = parsed.todo_count || 0;
    const summary = `Todos updated (${count} items)`;
    let body = '';
    if (parsed.todos && parsed.todos.length) {
        for (const t of parsed.todos) {
            const icon = {'completed': '\u2705', 'in_progress': '\u23f3', 'pending': '\u2b1c'}[t.status] || '\u2b1c';
            body += `<div>${icon} ${esc(t.content || '')}</div>`;
        }
    }
    return finishToolResult(summary, body);
}
