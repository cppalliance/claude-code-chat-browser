import { describe, expect, it } from 'vitest';
import { renderTodoWriteResult } from './todo_write.js';
import { mountToolResult, expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderTodoWriteResult', () => {
    it('renders todo items with emoji status icons', () => {
        const html = renderTodoWriteResult({
            result_type: 'todo_write',
            todos: [
                { status: 'pending', content: 'write tests' },
                { status: 'completed', content: 'fix bug' },
                { status: 'in_progress', content: 'review PR' },
            ],
        });
        expect(html).toContain('Todos updated (3 items)');
        expect(html).toContain('write tests');
        expect(html).toContain('fix bug');
        expect(html).toContain('review PR');
        expect(html).toContain('tool-result');
    });

    it('uses todo_count when todos array is absent', () => {
        const html = renderTodoWriteResult({
            result_type: 'todo_write',
            todo_count: 5,
        });
        expect(html).toContain('Todos updated (5 items)');
    });

    it('escapes HTML in todo content', () => {
        const html = mountToolResult({
            result_type: 'todo_write',
            todos: [{ status: 'pending', content: XSS_SCRIPT }],
        });
        expectNoRawHtml(html, [XSS_SCRIPT]);
        expect(html).toContain('&lt;script&gt;');
    });
});
