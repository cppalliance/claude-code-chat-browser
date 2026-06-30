import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { initToolTypesManifest } from './tool_types_manifest.js';
import { TOOL_USE_RENDERERS } from './registry.js';

describe('initToolTypesManifest', () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    afterEach(() => {
        vi.unstubAllGlobals();
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

        expect(warn).toHaveBeenCalledWith(
            '[tool registry] Backend tool type "FutureToolXYZ" has no TOOL_USE_RENDERERS entry',
        );
    });

    it('warns when fetch fails', async () => {
        const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')));

        await initToolTypesManifest();

        expect(warn).toHaveBeenCalledWith(
            '[tool registry] Could not load tool types manifest:',
            expect.any(Error),
        );
    });

    it('warns when fetch times out', async () => {
        vi.useFakeTimers();
        try {
            const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
            vi.stubGlobal(
                'fetch',
                vi.fn((_url, init) =>
                    new Promise((_resolve, reject) => {
                        init?.signal?.addEventListener('abort', () => {
                            reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
                        });
                    }),
                ),
            );

            const promise = initToolTypesManifest();
            await vi.advanceTimersByTimeAsync(5000);
            await promise;

            expect(warn).toHaveBeenCalledWith(
                '[tool registry] Could not load /static/tool_types.json: timed out after 5000ms',
            );
        } finally {
            vi.useRealTimers();
        }
    });
});
