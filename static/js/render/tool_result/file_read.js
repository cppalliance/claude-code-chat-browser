import { finishToolResult } from './common.js';

export function renderFileReadResult(parsed) {
    const numLines = parsed.num_lines ? ` (${parsed.num_lines} lines)` : '';
    const summary = `Read: ${parsed.file_path || ''}${numLines}`;
    return finishToolResult(summary, '');
}
