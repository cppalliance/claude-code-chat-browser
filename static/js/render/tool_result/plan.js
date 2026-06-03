import { finishToolResult } from './common.js';

export function renderPlanResult(parsed) {
    const summary = `Plan: ${parsed.file_path || ''}`;
    return finishToolResult(summary, '');
}
