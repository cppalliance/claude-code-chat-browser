import { finishToolResult } from './common.js';

export function renderToolResultFallback(parsed) {
    const rt = parsed.result_type || 'unknown';
    const summary = `Tool result (${rt})`;
    return finishToolResult(summary, '');
}
