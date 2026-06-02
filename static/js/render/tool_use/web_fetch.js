import { renderToolUseFallback } from './fallback.js';

/** Preserves pre-refactor JSON fallback body; registered so WebFetch does not hit generic unknown-tool path. */
export function renderWebFetchUse(tool) {
    return renderToolUseFallback({ ...tool, name: 'WebFetch' });
}
