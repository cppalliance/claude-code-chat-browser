import { TOOL_USE_RENDERERS } from './registry.js';

const MANIFEST_URL = '/static/tool_types.json';
const MANIFEST_FETCH_TIMEOUT_MS = 5000;

/**
 * Load backend tool-type manifest and cross-check ``TOOL_USE_RENDERERS``.
 * Logs ``console.warn`` when the backend list and frontend registry diverge.
 */
export async function initToolTypesManifest() {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), MANIFEST_FETCH_TIMEOUT_MS);
    try {
        const res = await fetch(MANIFEST_URL, { signal: controller.signal });
        if (!res.ok) {
            console.warn(`[tool registry] Could not load ${MANIFEST_URL}: HTTP ${res.status}`);
            return;
        }
        const data = await res.json();
        const types = Array.isArray(data.tool_types) ? data.tool_types : [];
        const manifest = new Set(types.filter((t) => typeof t === 'string'));

        for (const name of manifest) {
            if (!Object.prototype.hasOwnProperty.call(TOOL_USE_RENDERERS, name)) {
                console.warn(
                    `[tool registry] Backend tool type "${name}" has no TOOL_USE_RENDERERS entry`,
                );
            }
        }
        for (const name of Object.keys(TOOL_USE_RENDERERS)) {
            if (!manifest.has(name)) {
                console.warn(
                    `[tool registry] TOOL_USE_RENDERERS entry "${name}" is missing from ${MANIFEST_URL}`,
                );
            }
        }
    } catch (err) {
        if (err?.name === 'AbortError') {
            console.warn(
                `[tool registry] Could not load ${MANIFEST_URL}: timed out after ${MANIFEST_FETCH_TIMEOUT_MS}ms`,
            );
            return;
        }
        console.warn('[tool registry] Could not load tool types manifest:', err);
    } finally {
        clearTimeout(timeoutId);
    }
}
