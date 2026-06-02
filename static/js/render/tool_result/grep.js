import { finishToolResult } from './common.js';

export function renderGrepResult(parsed) {
    const summary = `Grep: ${parsed.num_files || 0} files, ${parsed.num_lines || 0} lines`;
    return finishToolResult(summary, '');
}
