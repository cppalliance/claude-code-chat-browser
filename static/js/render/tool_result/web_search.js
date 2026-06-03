import { finishToolResult } from './common.js';

export function renderWebSearchResult(parsed) {
    const summary = `Search: "${parsed.query || ''}" - ${parsed.result_count || 0} results`;
    return finishToolResult(summary, '');
}
