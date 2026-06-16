import { beforeEach, describe, expect, it, vi } from 'vitest';
import { showSearchPage, doSearch } from './search.js';

const SEARCH_HITS = [
    {
        project: 'alpha',
        session_id: 'sess-1',
        title: 'First hit',
        role: 'user',
        timestamp: '2026-05-19T10:00:00Z',
        snippet: 'matched keyword here',
    },
    {
        project: 'beta',
        session_id: 'sess-2',
        title: 'Second hit',
        role: 'assistant',
        timestamp: '2026-05-19T11:00:00Z',
        snippet: 'another line',
    },
];

describe('search page', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="content"></div>';
        vi.stubGlobal('fetch', vi.fn());
        window.location.hash = '';
    });

    it('showSearchPage renders the search UI and sets hash', () => {
        showSearchPage();
        expect(window.location.hash).toBe('#search');
        expect(document.getElementById('search-input')).not.toBeNull();
        expect(document.getElementById('search-results')).not.toBeNull();
        expect(document.getElementById('content').innerHTML).toContain('Search conversations');
    });

    it('doSearch renders results with snippet text', async () => {
        showSearchPage();
        fetch.mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(SEARCH_HITS),
        });
        document.getElementById('search-input').value = 'keyword';

        await doSearch();

        const results = document.getElementById('search-results');
        expect(results.innerHTML).toContain('2 results');
        expect(results.innerHTML).toContain('First hit');
        expect(results.innerHTML).toContain('matched keyword here');
        expect(results.querySelectorAll('.search-result').length).toBe(2);
    });

    it('doSearch shows empty state when no hits', async () => {
        showSearchPage();
        fetch.mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
        document.getElementById('search-input').value = 'nothing';

        await doSearch();

        const results = document.getElementById('search-results');
        expect(results.innerHTML).toContain('0 results');
        expect(results.innerHTML).toContain('No results found');
    });

    it('doSearch surfaces HTTP errors', async () => {
        showSearchPage();
        fetch.mockResolvedValue({ ok: false, status: 503, text: () => Promise.resolve('unavailable') });
        document.getElementById('search-input').value = 'fail';

        await doSearch();

        expect(document.getElementById('search-results').innerHTML).toContain('Error:');
        expect(document.getElementById('search-results').innerHTML).toContain('unavailable');
    });

    it('doSearch ignores stale responses when a newer request was started', async () => {
        showSearchPage();
        let resolveFirst;
        const first = new Promise((resolve) => { resolveFirst = resolve; });
        fetch
            .mockImplementationOnce(() => first.then(() => ({
                ok: true,
                json: () => Promise.resolve(SEARCH_HITS),
            })))
            .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([]) });

        document.getElementById('search-input').value = 'slow';
        const slow = doSearch();
        document.getElementById('search-input').value = 'fast';
        await doSearch();
        resolveFirst();
        await slow;

        expect(document.getElementById('search-results').innerHTML).toContain('0 results');
    });
});
