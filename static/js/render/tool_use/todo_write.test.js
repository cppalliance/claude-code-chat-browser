import { describe, expect, it } from 'vitest';
import { renderTodoWriteUse } from './todo_write.js';
import { mountToolUse, expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderTodoWriteUse', () => {
    it('renders todo items with status icons', () => {
        const html = renderTodoWriteUse({
            name: 'TodoWrite',
            input: {
                todos: [
                    { status: 'pending', content: 'first task' },
                    { status: 'completed', content: 'done task' },
                    { status: 'in_progress', content: 'active task' },
                ],
            },
        });
        expect(html).toContain('[ ] first task');
        expect(html).toContain('[x] done task');
        expect(html).toContain('[~] active task');
        expect(html).toContain('tool-call');
    });

    it('handles empty todos list', () => {
        const html = renderTodoWriteUse({
            name: 'TodoWrite',
            input: { todos: [] },
        });
        expect(html).toContain('TodoWrite');
        expect(html).toContain('tool-call');
    });

    it('escapes HTML in todo content', () => {
        const html = mountToolUse({
            name: 'TodoWrite',
            input: { todos: [{ status: 'pending', content: XSS_SCRIPT }] },
        });
        expectNoRawHtml(html, [XSS_SCRIPT]);
        expect(html).toContain('&lt;script&gt;');
    });
});
