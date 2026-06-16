import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { state } from './shared/state.js';

const showProjects = vi.fn();
const showWorkspace = vi.fn();
const loadSession = vi.fn();
const showSearchPage = vi.fn();
const toggleTheme = vi.fn();
const toggleSidebar = vi.fn();

vi.mock('./projects.js', () => ({ showProjects }));
vi.mock('./sessions.js', () => ({ showWorkspace, loadSession, selectSession: vi.fn(), copyAll: vi.fn() }));
vi.mock('./search.js', () => ({ showSearchPage, doSearch: vi.fn() }));
vi.mock('./export.js', () => ({ bulkExport: vi.fn(), downloadSession: vi.fn() }));
vi.mock('./shared/utils.js', async (importOriginal) => {
    const actual = await importOriginal();
    return { ...actual, toggleSidebar, closeSidebar: vi.fn() };
});
vi.mock('./shared/theme.js', () => ({
    HLJS_THEME_SHEETS: {},
    applyHljsTheme: vi.fn(),
    applyTheme: vi.fn(),
    toggleTheme,
    setWorkspaceMode: vi.fn(),
}));

describe('router (app.js)', () => {
    const origScrollTo = window.scrollTo;
    const origScrollIntoView = Element.prototype.scrollIntoView;

    beforeAll(async () => {
        window.scrollTo = vi.fn();
        Element.prototype.scrollIntoView = vi.fn();
        await import('./app.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));
    });

    afterAll(() => {
        window.scrollTo = origScrollTo;
        Element.prototype.scrollIntoView = origScrollIntoView;
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

describe('navbar handlers (app.js DOMContentLoaded)', () => {
    const origScrollTo = window.scrollTo;

    beforeAll(async () => {
        vi.resetModules();
        window.scrollTo = vi.fn();
        document.body.innerHTML = `
            <button id="hamburger-btn"></button>
            <a id="navbar-brand" href="#"></a>
            <a id="nav-search-link" href="#search"></a>
            <button id="theme-toggle"></button>
            <div id="content"></div>
            <span id="footer-year"></span>
        `;
        await import('./app.js');
        document.dispatchEvent(new Event('DOMContentLoaded'));
    });

    afterAll(() => {
        window.scrollTo = origScrollTo;
    });

    beforeEach(() => {
        toggleTheme.mockClear();
        toggleSidebar.mockClear();
        showProjects.mockClear();
        showSearchPage.mockClear();
    });

    it('wires hamburger click to toggleSidebar', () => {
        document.getElementById('hamburger-btn').click();
        expect(toggleSidebar).toHaveBeenCalledTimes(1);
    });

    it('wires navbar brand click to showProjects', () => {
        const brand = document.getElementById('navbar-brand');
        brand.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        expect(showProjects).toHaveBeenCalled();
    });

    it('wires nav search link click to showSearchPage', () => {
        const link = document.getElementById('nav-search-link');
        link.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        expect(showSearchPage).toHaveBeenCalled();
    });

    it('wires theme toggle click to toggleTheme', () => {
        document.getElementById('theme-toggle').click();
        expect(toggleTheme).toHaveBeenCalledTimes(1);
    });
});
