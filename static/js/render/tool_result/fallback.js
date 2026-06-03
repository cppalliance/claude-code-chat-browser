import { finishToolResult } from './common.js';
import { UNKNOWN_DISPATCH_KEY } from '../constants.js';

export function renderToolResultFallback(parsed) {
    const rt = parsed.result_type || UNKNOWN_DISPATCH_KEY;
    const summary = `Tool result (${rt})`;
    return finishToolResult(summary, '');
}
