import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { state } from './state.js';

function resetState() {
    state.currentProject = null;
    state.cachedSessions = [];
    state.projectDisplayNames = {};
    state.navInProgress = false;
}

describe('state', () => {
    beforeEach(() => {
        resetState();
    });

    afterEach(() => {
        resetState();
    });

    it('initializes with null current project', () => {
        expect(state.currentProject).toBeNull();
    });

    it('starts with empty cached sessions', () => {
        expect(state.cachedSessions).toEqual([]);
    });

    it('allows updating currentProject', () => {
        state.currentProject = 'test-project';
        expect(state.currentProject).toBe('test-project');
    });
});
