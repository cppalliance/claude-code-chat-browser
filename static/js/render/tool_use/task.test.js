import { describe, expect, it } from 'vitest';
import { renderTaskUse } from './task.js';
import { renderToolUse } from '../registry.js';
import { expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderTaskUse', () => {
    it('renders subagent type, description, and prompt', () => {
        const html = renderTaskUse({
            name: 'Task',
            input: {
                subagent_type: 'explore',
                description: 'find auth code',
                prompt: 'search for login handlers',
            },
        });
        expect(html).toContain('explore');
        expect(html).toContain('find auth code');
        expect(html).toContain('search for login handlers');
        expect(html).toContain('Prompt');
        expect(html).toContain('tool-call');
    });

    it('omits prompt section when prompt is absent', () => {
        const html = renderTaskUse({
            name: 'Task',
            input: { subagent_type: 'general', description: 'run tests' },
        });
        expect(html).toContain('run tests');
        expect(html).not.toContain('Prompt');
    });

    it('escapes HTML in task fields', () => {
        const html = renderToolUse({
            name: 'Task',
            input: {
                subagent_type: XSS_SCRIPT,
                description: '<evil>',
                prompt: '<script>run()</script>',
            },
        });
        expectNoRawHtml(html, [XSS_SCRIPT, '<evil>', '<script>']);
    });
});
