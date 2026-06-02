import { describe, it, expect } from 'vitest';
import {
    TOOL_USE_RENDERERS,
    TOOL_RESULT_RENDERERS,
    renderToolUse,
    renderToolResult,
    getToolSummary,
    toolResultHasBody,
} from './registry.js';
import { UNKNOWN_DISPATCH_KEY } from './constants.js';
import { renderWebFetchUse } from './tool_use/web_fetch.js';

const CORE_TOOL_USE = ['Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep', 'Task', 'TodoWrite', 'AskUserQuestion', 'WebFetch', 'WebSearch'];

const CORE_TOOL_RESULT = [
    'bash',
    'file_read',
    'file_edit',
    'file_write',
    'glob',
    'grep',
    'web_search',
    'web_fetch',
    'task',
    'todo_write',
    'user_input',
    'plan',
];

describe('TOOL_USE_RENDERERS', () => {
    it('registers core tool names', () => {
        for (const name of CORE_TOOL_USE) {
            expect(TOOL_USE_RENDERERS[name], name).toBeTypeOf('function');
        }
    });

    it('does not register the unknown dispatch sentinel as a tool renderer', () => {
        expect(Object.prototype.hasOwnProperty.call(TOOL_USE_RENDERERS, UNKNOWN_DISPATCH_KEY)).toBe(false);
    });

    it('renderBashUse escapes HTML in command', () => {
        const html = renderToolUse({
            name: 'Bash',
            input: { command: '<script>alert(1)</script>' },
        });
        expect(html).not.toContain('<script>');
        expect(html).toContain('&lt;script&gt;');
    });

    it('returns empty string for null or undefined tool', () => {
        expect(renderToolUse(null)).toBe('');
        expect(renderToolUse(undefined)).toBe('');
    });

    it('renderReadUse escapes file path in body and summary', () => {
        const html = renderToolUse({
            name: 'Read',
            input: { file_path: 'C:\\tmp\\<evil>.txt' },
        });
        expect(html).toContain('&lt;evil&gt;');
        expect(html).not.toContain('<evil>');
    });
});

describe('TOOL_RESULT_RENDERERS', () => {
    it('registers core result types', () => {
        for (const rt of CORE_TOOL_RESULT) {
            expect(TOOL_RESULT_RENDERERS[rt], rt).toBeTypeOf('function');
        }
    });

    it('renderBashResult escapes stdout', () => {
        const html = renderToolResult({
            result_type: 'bash',
            exit_code: 0,
            stdout: '<img onerror=alert(1)>',
        });
        expect(html).not.toContain('<img');
        expect(html).toContain('&lt;img');
    });

    it('renderBashResult avoids undefined in summary when exit_code missing', () => {
        const html = renderToolResult({ result_type: 'bash' });
        expect(html).toContain('Bash Result (unknown)');
        expect(html).not.toContain('undefined');
    });

    it('returns empty string for null or undefined parsed', () => {
        expect(renderToolResult(null)).toBe('');
        expect(renderToolResult(undefined)).toBe('');
    });
});

describe('toolResultHasBody', () => {
    it('returns false for null or undefined', () => {
        expect(toolResultHasBody(null)).toBe(false);
        expect(toolResultHasBody(undefined)).toBe(false);
    });

    it('returns true for bash with stdout or stderr', () => {
        expect(toolResultHasBody({ result_type: 'bash', stdout: 'ok' })).toBe(true);
        expect(toolResultHasBody({ result_type: 'bash', stderr: 'err' })).toBe(true);
        expect(toolResultHasBody({ result_type: 'bash' })).toBe(false);
    });

    it('returns false for summary-only result types', () => {
        expect(toolResultHasBody({ result_type: 'file_read', file_path: '/a' })).toBe(false);
        expect(toolResultHasBody({ result_type: 'glob', num_files: 3 })).toBe(false);
    });

    it('returns true for user_input and todo_write with todos', () => {
        expect(toolResultHasBody({ result_type: 'user_input' })).toBe(true);
        expect(toolResultHasBody({ result_type: 'todo_write', todos: [{ content: 'x' }] })).toBe(true);
        expect(toolResultHasBody({ result_type: 'todo_write', todo_count: 1 })).toBe(false);
    });

    it('returns true for task when duration, retrieval, or description is set', () => {
        expect(toolResultHasBody({ result_type: 'task', description: 'subagent' })).toBe(true);
        expect(toolResultHasBody({ result_type: 'task', total_duration_ms: 100 })).toBe(true);
        expect(toolResultHasBody({ result_type: 'task', status: 'completed' })).toBe(false);
    });
});

describe('getToolSummary', () => {
    it('formats Bash summary', () => {
        expect(getToolSummary('Bash', { command: 'ls -la' })).toMatch(/Bash:/);
        expect(getToolSummary('Bash', { command: 'ls -la' })).toContain('ls -la');
    });

    it('formats Read summary as plain text (escaping deferred to wrapToolUse)', () => {
        expect(getToolSummary('Read', { file_path: 'a<b' })).toBe('Read: a<b');
    });
});

describe('renderToolUse fallback', () => {
    it('uses JSON fallback for unknown tools', () => {
        const html = renderToolUse({
            name: 'UnknownToolXYZ',
            input: { foo: 'bar' },
        });
        expect(html).toContain('tool-call');
        expect(html).toContain('&quot;foo&quot;');
        expect(TOOL_USE_RENDERERS.UnknownToolXYZ).toBeUndefined();
    });

    it('uses fallback when name is an inherited property (e.g. constructor)', () => {
        const html = renderToolUse({
            name: 'constructor',
            input: { foo: 'bar' },
        });
        expect(html).toContain('tool-call');
        expect(html).toContain('&quot;foo&quot;');
    });

    it('dispatches WebFetch to registered renderer (not generic unknown-tool fallback)', () => {
        expect(TOOL_USE_RENDERERS.WebFetch).toBe(renderWebFetchUse);
        const html = renderToolUse({
            name: 'WebFetch',
            input: { url: 'https://example.com' },
        });
        expect(html).toContain('tool-call');
        expect(html).toContain('example.com');
    });

    it('renders WebSearch via registry', () => {
        const html = renderToolUse({
            name: 'WebSearch',
            input: { query: 'vitest registry' },
        });
        expect(html).toContain('tool-call');
        expect(html).toContain('vitest registry');
    });
});

describe('renderTodoWriteResult', () => {
    it('summary count matches parsed.todos length when todos are present', () => {
        const html = renderToolResult({
            result_type: 'todo_write',
            todo_count: 99,
            todos: [
                { status: 'pending', content: 'one' },
                { status: 'completed', content: 'two' },
            ],
        });
        expect(html).toContain('Todos updated (2 items)');
        expect(html).not.toContain('99 items');
    });
});

describe('renderToolResult fallback', () => {
    it('renders summary-only for unknown result types', () => {
        const html = renderToolResult({ result_type: 'custom_type' });
        expect(html).toContain('Tool result (custom_type)');
        expect(html).toContain('tool-result');
    });

    it('uses fallback when result_type is an inherited property (e.g. constructor)', () => {
        const html = renderToolResult({ result_type: 'constructor' });
        expect(html).toContain('Tool result (constructor)');
        expect(html).toContain('tool-result');
        expect(Object.prototype.hasOwnProperty.call(TOOL_RESULT_RENDERERS, 'constructor')).toBe(false);
    });
});
