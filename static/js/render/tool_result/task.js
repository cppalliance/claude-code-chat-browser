import { finishToolResult } from './common.js';

export function renderTaskResult(parsed) {
    const status = parsed.status || 'completed';
    const dur = parsed.total_duration_ms;
    const durStr = dur ? ` (${(dur / 1000).toFixed(1)}s)` : '';
    const tokStr = parsed.total_tokens ? `, ${parsed.total_tokens.toLocaleString()} tokens` : '';
    const toolStr = parsed.total_tool_use_count ? `, ${parsed.total_tool_use_count} tool calls` : '';
    let summary = `Task ${status}${durStr}${tokStr}${toolStr}`;
    if (parsed.retrieval_status) summary = `Task retrieval: ${parsed.retrieval_status}`;
    if (parsed.description) summary = `Task launched: ${parsed.description}`;
    return finishToolResult(summary, '');
}
