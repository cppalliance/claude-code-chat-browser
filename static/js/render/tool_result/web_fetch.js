import { finishToolResult } from './common.js';

export function renderWebFetchResult(parsed) {
    const summary = `Fetch: ${parsed.url || ''} (${parsed.status_code || '?'})`;
    return finishToolResult(summary, '');
}
