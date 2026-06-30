import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { initToolTypesManifest } from './tool_types_manifest.js';
import { getManifestToolTypes, setManifestToolTypes } from './tool_types_state.js';
import { TOOL_USE_RENDERERS } from './registry.js';

// Registry drift warnings are asserted here (init-time cross-check only; no per-render warn).

describe('initToolTypesManifest', () => {
    beforeEach(() => {
        setManifestToolTypes(null);
        vi.restoreAllMocks();
    });

    afterEach(() => {
        setManifestToolTypes(null);
    });

    it('cross-checks manifest against TOOL_USE_RENDERERS and warns on drift', async () => {
        const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
        const manifestTypes = [...Object.keys(TOOL_USE_RENDERERS), 'FutureToolXYZ'];
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({
                ok: true,
                json: async () => ({ tool_types: manifestTypes }),
            }),
        );

        await initToolTypesManifest();

        expect(getManifestToolTypes()).toEqual(new Set(manifestTypes));
        expect(warn).toHaveBeenCalledWith(
            '[tool registry] Backend tool type "FutureToolXYZ" has no TOOL_USE_RENDERERS entry',
        );
    });

    it('warns when fetch fails', async () => {
        const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')));

        await initToolTypesManifest();

        expect(getManifestToolTypes()).toBeNull();
        expect(warn).toHaveBeenCalledWith(
            '[tool registry] Could not load tool types manifest:',
            expect.any(Error),
        );
    });
});
