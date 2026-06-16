import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { state } from './shared/state.js';

const showProjects = vi.fn();
const showWorkspace = vi.fn();
const loadSession = vi.fn();
const showSearchPage = vi.fn();

vi.mock('./projects.js', () => ({ showProjects }));
vi.mock('./sessions.js', () => ({ showWorkspace, loadSession, selectSession: vi.fn(), copyAll: vi.fn() }));
vi.mock('./search.js', () => ({ showSearchPage, doSearch: vi.fn() }));
vi.mock('./export.js', () => ({ bulkExport: vi.fn(), downloadSession: vi.fn() }));
vi.mock('./shared/theme.js', () => ({
    HLJS_THEME_SHEETS: {},
    applyHljsTheme: vi.fn(),
    applyTheme: vi.fn(),
    toggleTheme: vi.fn(),
    setWorkspaceMode: vi.fn(),
}));

describe('router (app.js)', () => {
    beforeAll(async () => {
        window.scrollTo = vi.fn();
        Element.prototype.scrollIntoView = vi.fn();
        await import('./app.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));
    });

    beforeEach(() => {
        document.body.innerHTML = '<div id="content"></div><span id="footer-year"></span>';
        state.currentProject = null;
        state.cachedSessions = [];
        state.navInProgress = false;
        showProjects.mockClear();
        showWorkspace.mockClear();
        loadSession.mockClear();
        showSearchPage.mockClear();
        window.location.hash = '';
        localStorage.clear();
    });

    function routeTo(hash) {
        window.location.hash = hash;
        window.dispatchEvent(new HashChangeEvent('hashchange'));
    }

    it('dispatches default hash to showProjects', () => {
        routeTo('');
        expect(showProjects).toHaveBeenCalled();
    });

    it('dispatches #search to showSearchPage on hashchange', () => {
        showProjects.mockClear();
        routeTo('#search');
        expect(showSearchPage).toHaveBeenCalledTimes(1);
        expect(showProjects).not.toHaveBeenCalled();
    });

    it('dispatches #project/<name> to showWorkspace', () => {
        showProjects.mockClear();
        routeTo('#project/my-project');
        expect(showWorkspace).toHaveBeenCalledWith('my-project');
    });

    it('dispatches #project/<name>/<sessionId> to showWorkspace when cache is cold', () => {
        routeTo('#project/my-project/sess-abc');
        expect(showWorkspace).toHaveBeenCalledWith('my-project', 'sess-abc');
        expect(loadSession).not.toHaveBeenCalled();
    });

    it('loads session from cache when project matches and sidebar exists', () => {
        state.currentProject = 'my-project';
        state.cachedSessions = [{ id: 'sess-abc' }];
        document.body.innerHTML += '<div id="sidebar"><button class="sidebar-item" id="sidebar-sess-abc"></button></div>';
        routeTo('#project/my-project/sess-abc');
        expect(loadSession).toHaveBeenCalledWith('my-project', 'sess-abc');
        expect(showWorkspace).not.toHaveBeenCalled();
        expect(document.getElementById('sidebar-sess-abc').classList.contains('active')).toBe(true);
    });

    it('falls back to showProjects when project name is a malformed URI', () => {
        showProjects.mockClear();
        routeTo('#project/%E0%A4%A');
        expect(showProjects).toHaveBeenCalled();
        expect(showWorkspace).not.toHaveBeenCalled();
    });

    it('falls back to showProjects when session project segment is malformed', () => {
        showProjects.mockClear();
        routeTo('#project/%E0%A4%A/sess-1');
        expect(showProjects).toHaveBeenCalled();
        expect(showWorkspace).not.toHaveBeenCalled();
    });

    it('re-runs routing when hashchange fires', () => {
        showProjects.mockClear();
        routeTo('#search');
        expect(showSearchPage).toHaveBeenCalledTimes(1);
        showSearchPage.mockClear();
        routeTo('#project/other');
        expect(showWorkspace).toHaveBeenCalledWith('other');
    });
});
