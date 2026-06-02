import { renderToolUseFallback } from './fallback.js';

/** Preserves pre-refactor JSON fallback body; registered so WebSearch does not hit generic unknown-tool path. */
export function renderWebSearchUse(tool) {
    return renderToolUseFallback({ ...tool, name: 'WebSearch' });
}
