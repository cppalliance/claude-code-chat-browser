// Export and download — bulk export, per-session download, file handle helpers.

import { showToast, showConfirm } from './shared/utils.js';
import { showProjects } from './projects.js';

// ==================== Export ====================

export function bulkExport(since = 'all') {
    const label = since === 'incremental' ? 'Export new sessions since last export?' : 'Export all sessions as a zip file?';
    showConfirm(label, async () => {
        const suffix = since === 'incremental' ? '-incremental' : '';
        const fname = `claude-code-export${suffix}-${new Date().toISOString().slice(0, 10)}.zip`;
        const handle = await getFileHandle(fname, [{ description: 'ZIP archive', accept: { 'application/zip': ['.zip'] } }]);
        if (!handle) return;
        const btnId = since === 'incremental' ? '#btn-export-since' : '#btn-export-all';
        const btn = document.querySelector(btnId);
        const origText = btn ? btn.textContent.trim() : '';
        if (btn) { btn.disabled = true; btn.textContent = 'Exporting...'; }
        try {
            const res = await fetch('/api/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ since }),
            });
            const ct = res.headers.get('Content-Type') || '';
            if (!res.ok) {
                let msg = `Export failed: ${res.status}`;
                if (ct.includes('application/json')) {
                    try {
                        const errBody = await res.json();
                        if (errBody.error) msg = errBody.error;
                    } catch (_) { /* ignore */ }
                }
                throw new Error(msg);
            }
            const blob = await res.blob();
            await writeToHandle(handle, blob, fname);
            showProjects();
        } catch (e) {
            showToast('Export failed: ' + e.message, 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = origText; }
        }
    });
}

export async function downloadSession(project, sessionId) {
    const fname = `session-${sessionId.slice(0, 8)}.md`;
    const handle = await getFileHandle(fname, [{ description: 'Markdown', accept: { 'text/markdown': ['.md'] } }]);
    if (!handle) return;
    try {
        const res = await fetch(`/api/export/session/${encodeURIComponent(project)}/${encodeURIComponent(sessionId)}`);
        if (!res.ok) throw new Error(`Download failed: ${res.status}`);
        const blob = await res.blob();
        await writeToHandle(handle, blob, fname);
    } catch (e) {
        showToast('Download failed: ' + e.message, 'error');
    }
}

async function getFileHandle(suggestedName, fileTypes) {
    if (window.showSaveFilePicker) {
        try {
            return await window.showSaveFilePicker({ suggestedName, types: fileTypes });
        } catch (e) {
            if (e.name === 'AbortError') return null;
        }
    }
    return 'fallback';
}

async function writeToHandle(handle, blob, fallbackName) {
    if (handle !== 'fallback') {
        const writable = await handle.createWritable();
        try {
            await writable.write(blob);
            await writable.close();
        } catch (e) {
            try { await writable.abort(); } catch { /* ignore abort errors */ }
            throw e;
        }
    } else {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fallbackName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
}
