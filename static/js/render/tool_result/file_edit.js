import { finishToolResult } from './common.js';

export function renderFileEditResult(parsed) {
    const summary = `Edited: ${parsed.file_path || ''}`;
    return finishToolResult(summary, '');
}
