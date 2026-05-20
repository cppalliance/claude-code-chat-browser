import { describe, it, expect } from 'vitest';
import { state } from './state.js';

describe('state', () => {
    it('initializes with null current project', () => {
        expect(state.currentProject).toBeNull();
    });

    it('starts with empty cached sessions', () => {
        expect(state.cachedSessions).toEqual([]);
    });

    it('allows updating currentProject', () => {
        state.currentProject = 'test-project';
        expect(state.currentProject).toBe('test-project');
        state.currentProject = null;
    });
});
