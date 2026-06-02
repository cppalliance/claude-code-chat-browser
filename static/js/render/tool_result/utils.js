export function toolResultHasBody(parsed) {
    const rt = parsed.result_type || 'unknown';
    if (rt === 'bash') return !!(parsed.stdout || parsed.stderr);
    if (rt === 'todo_write') return !!(parsed.todos && parsed.todos.length);
    if (rt === 'user_input') return true;
    if (rt === 'task' && (parsed.total_duration_ms || parsed.retrieval_status || parsed.description)) return true;
    return false;
}
