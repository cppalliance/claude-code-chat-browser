import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { bulkExport, downloadSession } from './export.js';

vi.mock('./projects.js', () => ({ showProjects: vi.fn() }));

import { showProjects } from './projects.js';

const mockWritable = {
    write: vi.fn(() => Promise.resolve()),
    close: vi.fn(() => Promise.resolve()),
    abort: vi.fn(() => Promise.resolve()),
};

const mockHandle = {
    createWritable: vi.fn(() => Promise.resolve(mockWritable)),
};

describe('export', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <button id="btn-export-all">Export all</button>
            <button id="btn-export-since">Export since</button>
        `;
        vi.stubGlobal('fetch', vi.fn());
        vi.stubGlobal('showSaveFilePicker', vi.fn(() => Promise.resolve(mockHandle)));
        mockWritable.write.mockClear();
        mockWritable.close.mockClear();
        mockHandle.createWritable.mockClear();
        showProjects.mockClear();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    async function confirmExport() {
        const ok = document.querySelector('.confirm-ok');
        expect(ok).not.toBeNull();
        ok.click();
        await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
    }

    it('bulkExport shows progress then completes on success', async () => {
        fetch.mockResolvedValue({
            ok: true,
            headers: { get: () => 'application/zip' },
            blob: () => Promise.resolve(new Blob(['zip'], { type: 'application/zip' })),
        });

        bulkExport('all');
        const btn = document.getElementById('btn-export-all');
        expect(btn.disabled).toBe(false);
        await confirmExport();

        expect(btn.textContent.trim()).toBe('Export all');
        expect(btn.disabled).toBe(false);
        expect(mockHandle.createWritable).toHaveBeenCalled();
        expect(showProjects).toHaveBeenCalled();
        expect(fetch).toHaveBeenCalledWith('/api/export', expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({ since: 'all' }),
        }));
    });

    it('bulkExport surfaces 5xx errors via toast', async () => {
        fetch.mockResolvedValue({
            ok: false,
            status: 500,
            headers: { get: () => 'application/json' },
            json: () => Promise.resolve({ error: 'export failed' }),
        });

        bulkExport('all');
        await confirmExport();
        await vi.waitFor(() => expect(document.querySelector('.toast-error')).not.toBeNull());

        expect(document.querySelector('.toast-error').textContent).toContain('export failed');
        expect(showProjects).not.toHaveBeenCalled();
    });

    it('bulkExport surfaces 4xx errors via toast', async () => {
        fetch.mockResolvedValue({
            ok: false,
            status: 403,
            headers: { get: () => 'text/plain' },
        });

        bulkExport('incremental');
        await confirmExport();
        await vi.waitFor(() => expect(document.querySelector('.toast-error')).not.toBeNull());

        expect(document.querySelector('.toast-error').textContent).toContain('Export failed: 403');
    });

    it('downloadSession writes a blob via the file picker', async () => {
        fetch.mockResolvedValue({
            ok: true,
            blob: () => Promise.resolve(new Blob(['# markdown'], { type: 'text/markdown' })),
        });

        await downloadSession('alpha', 'sess-abcdef12');

        expect(fetch).toHaveBeenCalledWith('/api/export/session/alpha/sess-abcdef12');
        expect(mockWritable.write).toHaveBeenCalled();
        expect(mockWritable.close).toHaveBeenCalled();
    });

    it('downloadSession falls back to blob URL when file picker is unavailable', async () => {
        vi.stubGlobal('showSaveFilePicker', undefined);
        const createObjectURL = vi.fn(() => 'blob:fake-url');
        const revokeObjectURL = vi.fn();
        vi.stubGlobal('URL', { createObjectURL, revokeObjectURL });
        const click = vi.fn();
        const anchor = document.createElement('a');
        anchor.click = click;
        const createElement = document.createElement.bind(document);
        vi.spyOn(document, 'createElement').mockImplementation((tag) => {
            if (tag === 'a') return anchor;
            return createElement(tag);
        });

        fetch.mockResolvedValue({
            ok: true,
            blob: () => Promise.resolve(new Blob(['content'], { type: 'text/markdown' })),
        });

        await downloadSession('alpha', 'sess-abcdef12');

        expect(createObjectURL).toHaveBeenCalled();
        expect(anchor.download).toBe('session-sess-abc.md');
        expect(click).toHaveBeenCalled();
    });
});
