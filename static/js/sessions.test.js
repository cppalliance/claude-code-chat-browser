import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { state } from './shared/state.js';
import { showWorkspace, loadSession, selectSession, copyAll } from './sessions.js';

// Session list + detail shapes mirror models/session.py (ProjectSessionRowDict / SessionDict).
const SESSION_LIST = [
    {
        id: 'sess-1',
        path: '/data/sess-1.jsonl',
        size_bytes: 1024,
        modified: 1716112800,
        title: 'First chat',
        models: ['claude-sonnet'],
        first_timestamp: '2026-05-19T10:00:00Z',
        last_timestamp: '2026-05-19T10:30:00Z',
    },
    {
        id: 'sess-2',
        path: '/data/sess-2.jsonl',
        size_bytes: 2048,
        modified: 1716116400,
        title: 'Second chat',
        models: ['claude-opus'],
        first_timestamp: '2026-05-19T11:00:00Z',
        last_timestamp: '2026-05-19T11:15:00Z',
    },
];

const SESSION_DETAIL = {
    session_id: 'sess-1',
    title: 'First chat',
    messages: [
        { role: 'user', text: 'Hello world', timestamp: '2026-05-19T10:00:00Z' },
        {
            role: 'assistant',
            text: 'Hi there',
            timestamp: '2026-05-19T10:01:00Z',
            model: 'claude-sonnet',
            usage: { output_tokens: 12 },
        },
    ],
    metadata: {
        models_used: ['claude-sonnet'],
        total_input_tokens: 10,
        total_output_tokens: 20,
        total_tool_calls: 0,
        compactions: 0,
        first_timestamp: '2026-05-19T10:00:00Z',
        last_timestamp: '2026-05-19T10:30:00Z',
    },
};

const NO_DRIFT_REPORT = {
    known_fields: ['type'],
    new_fields: [],
    missing_fields: [],
    has_drift: false,
};

const DRIFT_REPORT = {
    known_fields: ['type'],
    new_fields: ['tool', 'tool.type'],
    missing_fields: [],
    has_drift: true,
};

function mockWorkspaceFetch({ schemaReport = NO_DRIFT_REPORT } = {}) {
    const callOrder = [];
    fetch.mockImplementation((url) => {
        callOrder.push(url);
        if (url === '/api/projects') {
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve([{ name: 'alpha', display_name: 'Alpha' }]),
            });
        }
        if (url === '/api/schema-report') {
            return Promise.resolve({ ok: true, json: () => Promise.resolve(schemaReport) });
        }
        if (url === '/api/projects/alpha/sessions') {
            return Promise.resolve({ ok: true, json: () => Promise.resolve(SESSION_LIST) });
        }
        if (url.startsWith('/api/sessions/alpha/')) {
            const sessionId = decodeURIComponent(url.split('/').pop());
            const row = SESSION_LIST.find((s) => s.id === sessionId) ?? SESSION_LIST[0];
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve({
                    ...SESSION_DETAIL,
                    session_id: sessionId,
                    title: row.title,
                }),
            });
        }
        return Promise.reject(new Error(`unexpected fetch: ${url}`));
    });
    return callOrder;
}

describe('sessions workspace', () => {
    let clipboardRestore;

    beforeEach(() => {
        document.body.innerHTML = '<div id="content"></div>';
        state.currentProject = null;
        state.cachedSessions = [];
        state.projectDisplayNames = {};
        vi.stubGlobal('fetch', vi.fn());
        window.location.hash = '';
        sessionStorage.clear();
    });

    afterEach(() => {
        if (clipboardRestore) {
            Object.defineProperty(navigator, 'clipboard', {
                value: clipboardRestore,
                configurable: true,
                writable: true,
            });
            clipboardRestore = null;
        }
        vi.unstubAllGlobals();
    });

    it('showWorkspace populates the sidebar with session entries', async () => {
        mockWorkspaceFetch();
        await showWorkspace('alpha');

        const sidebar = document.getElementById('sidebar');
        expect(sidebar).not.toBeNull();
        expect(sidebar.innerHTML).toContain('First chat');
        expect(sidebar.innerHTML).toContain('Second chat');
        expect(sidebar.querySelectorAll('.sidebar-item').length).toBe(2);
        expect(state.cachedSessions).toHaveLength(2);
    });

    it('showWorkspace marks the selected session active in the sidebar', async () => {
        mockWorkspaceFetch();
        await showWorkspace('alpha', 'sess-2');

        const active = document.querySelector('.sidebar-item.active');
        expect(active).not.toBeNull();
        expect(active.id).toBe('sidebar-sess-2');
    });

    it('showWorkspace fetches schema report after sessions load', async () => {
        const callOrder = mockWorkspaceFetch();
        await showWorkspace('alpha');

        const sessionsIdx = callOrder.indexOf('/api/projects/alpha/sessions');
        const schemaIdx = callOrder.indexOf('/api/schema-report');
        expect(sessionsIdx).toBeGreaterThanOrEqual(0);
        expect(schemaIdx).toBeGreaterThan(sessionsIdx);
    });

    it('showWorkspace renders schema drift banner when report has drift', async () => {
        mockWorkspaceFetch({ schemaReport: DRIFT_REPORT });
        await showWorkspace('alpha');

        const banner = document.getElementById('schema-drift-banner');
        expect(banner).not.toBeNull();
        expect(banner.textContent).toContain('Upstream JSONL schema drift detected');
        expect(banner.textContent).toContain('tool');
    });

    it('loadSession renders messages in the main panel', async () => {
        mockWorkspaceFetch();
        await showWorkspace('alpha');
        await loadSession('alpha', 'sess-1');

        const panel = document.getElementById('session-content');
        expect(panel.innerHTML).toContain('First chat');
        expect(panel.innerHTML).toContain('Hello world');
        expect(panel.innerHTML).toContain('Hi there');
        expect(panel.querySelector('.bubble-user')).not.toBeNull();
        expect(panel.querySelector('.bubble-ai')).not.toBeNull();
    });

    it('loadSession surfaces HTTP errors', async () => {
        document.body.innerHTML = '<div id="content"><div id="session-content"></div></div>';
        fetch.mockResolvedValue({
            ok: false,
            status: 404,
            statusText: 'Not Found',
            json: () => Promise.resolve({ error: 'missing session' }),
        });

        await loadSession('alpha', 'missing');

        expect(document.getElementById('session-content').innerHTML).toContain('missing session');
    });

    it('selectSession updates the location hash', () => {
        selectSession('alpha', 'sess-2');
        expect(window.location.hash).toBe('#project/alpha/sess-2');
    });

    it('copyAll writes session text to the clipboard', async () => {
        const writeText = vi.fn(() => Promise.resolve());
        clipboardRestore = navigator.clipboard;
        Object.defineProperty(navigator, 'clipboard', {
            value: { writeText },
            configurable: true,
            writable: true,
        });
        const el = document.createElement('div');
        el.className = 'session-content-inner';
        el.textContent = 'Line one\nLine two';
        Object.defineProperty(el, 'innerText', { get: () => el.textContent });
        document.body.appendChild(el);

        copyAll();

        await vi.waitFor(() => expect(writeText).toHaveBeenCalledWith('Line one\nLine two'));
    });
});
