import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { showSearchPage, doSearch, highlightSnippet } from './search.js';

// SearchHitDict[] — mirrors models/search.py.
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

describe('highlightSnippet', () => {
    it('wraps a case-insensitive match in mark after escaping', () => {
        const html = highlightSnippet('matched keyword here', 'Keyword');
        expect(html).toContain('<mark>keyword</mark>');
        expect(html).not.toContain('<script>');
    });

    it('does not inject raw HTML from session content', () => {
        const html = highlightSnippet('<img onerror=alert(1)>', 'img');
        expect(html).toContain('&lt;');
        expect(html).not.toContain('<img onerror');
        expect(html).not.toContain('<script>');
    });
});

describe('search page', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="content"></div>';
        vi.stubGlobal('fetch', vi.fn());
        window.location.hash = '';
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('showSearchPage renders the search UI and sets hash', () => {
        showSearchPage();
        expect(window.location.hash).toBe('#search');
        expect(document.getElementById('search-input')).not.toBeNull();
        expect(document.getElementById('search-results')).not.toBeNull();
        expect(document.getElementById('search-all-history')).not.toBeNull();
        expect(document.getElementById('content').innerHTML).toContain('30 days');
    });

    it('doSearch prompts when query is empty', async () => {
        showSearchPage();
        document.getElementById('search-input').value = '   ';

        await doSearch();

        expect(document.getElementById('search-results').innerHTML).toContain('Enter a search term');
        expect(fetch).not.toHaveBeenCalled();
    });

    it('doSearch renders results with highlighted snippet text', async () => {
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
        expect(results.innerHTML).toContain('<mark>keyword</mark>');
        expect(results.querySelectorAll('.search-result').length).toBe(2);
    });

    it('doSearch sends all_history when checkbox is checked', async () => {
        showSearchPage();
        fetch.mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
        document.getElementById('search-input').value = 'old';
        document.getElementById('search-all-history').checked = true;

        await doSearch();

        expect(fetch).toHaveBeenCalledWith(expect.stringContaining('all_history=1'));
    });

    it('doSearch shows empty state when no hits', async () => {
        showSearchPage();
        fetch.mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
        document.getElementById('search-input').value = 'nothing';

        await doSearch();

        const results = document.getElementById('search-results');
        expect(results.innerHTML).toContain('0 results');
        expect(results.innerHTML).toContain('search-empty');
        expect(results.innerHTML).not.toContain('search-error');
    });

    it('doSearch shows truncation warning when results hit the limit', async () => {
        showSearchPage();
        const full = Array.from({ length: 50 }, (_, i) => ({
            ...SEARCH_HITS[0],
            session_id: `sess-${i}`,
        }));
        fetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(full) });
        document.getElementById('search-input').value = 'keyword';

        await doSearch();

        expect(document.getElementById('search-results').innerHTML).toContain('search-truncation');
    });

    it('doSearch surfaces structured API errors with data-error-code', async () => {
        showSearchPage();
        fetch.mockResolvedValue({
            ok: false,
            status: 503,
            json: () => Promise.resolve({
                error: 'Search index is temporarily unavailable',
                code: 'SEARCH_INDEX_UNAVAILABLE',
            }),
        });
        document.getElementById('search-input').value = 'fail';

        await doSearch();

        const err = document.querySelector('.search-error');
        expect(err).not.toBeNull();
        expect(err.getAttribute('data-error-code')).toBe('SEARCH_INDEX_UNAVAILABLE');
        expect(err.textContent).toContain('temporarily unavailable');
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
