// Shared mutable app state — any module that reads or writes cross-route state imports this.
export const state = {
    currentProject: null,
    cachedSessions: [],
    projectDisplayNames: {},
    navInProgress: false,
};
