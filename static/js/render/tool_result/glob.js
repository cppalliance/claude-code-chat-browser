import { finishToolResult } from './common.js';

export function renderGlobResult(parsed) {
    const trunc = parsed.truncated ? ' (truncated)' : '';
    const summary = `Glob: ${parsed.num_files || 0} files found${trunc}`;
    return finishToolResult(summary, '');
}
