import { finishToolResult } from './common.js';

export function renderFileWriteResult(parsed) {
    const summary = `Wrote: ${parsed.file_path || ''}`;
    return finishToolResult(summary, '');
}
