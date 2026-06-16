import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { showProjects } from './projects.js';

// ProjectDict[] — mirrors models/project.py.
const PROJECT_FIXTURE = [
    {
        name: 'alpha',
        path: '/data/alpha',
        display_name: 'Alpha Project',
        session_count: 2,
        last_modified: '2026-05-19T10:00:00Z',
    },
    {
        name: 'beta',
        path: '/data/beta',
        display_name: 'Beta Project',
        session_count: 0,
        last_modified: '2026-05-18T10:00:00Z',
    },
];

describe('showProjects', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="content"></div>';
        vi.stubGlobal('fetch', vi.fn());
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('renders project cards from the API response', async () => {
        fetch.mockImplementation((url) => {
            if (url === '/api/projects') {
                return Promise.resolve({ ok: true, json: () => Promise.resolve(PROJECT_FIXTURE) });
            }
            if (url === '/api/export/state') {
                return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
            }
            return Promise.reject(new Error(`unexpected fetch: ${url}`));
        });

        await showProjects();

        const content = document.getElementById('content');
        expect(content.innerHTML).toContain('Alpha Project');
        expect(content.innerHTML).toContain('2 sessions');
        expect(content.innerHTML).toContain('Projects without Sessions');
        expect(content.innerHTML).toContain('Beta Project');
    });

    it('shows empty state when no projects are returned', async () => {
        fetch.mockImplementation((url) => {
            if (url === '/api/projects') {
                return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
            }
            return Promise.reject(new Error(`unexpected fetch: ${url}`));
        });

        await showProjects();

        const content = document.getElementById('content');
        expect(content.innerHTML).toContain('empty-state');
        expect(content.innerHTML).toContain('No Claude Code projects found');
    });

    it('surfaces API errors', async () => {
        fetch.mockImplementation((url) => {
            if (url === '/api/projects') {
                return Promise.resolve({
                    ok: false,
                    status: 500,
                    json: () => Promise.resolve({ error: 'disk unavailable' }),
                });
            }
            return Promise.reject(new Error(`unexpected fetch: ${url}`));
        });

        await showProjects();

        expect(document.getElementById('content').innerHTML).toContain('disk unavailable');
    });
});
