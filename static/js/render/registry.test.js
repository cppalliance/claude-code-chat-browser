import { describe, it, expect } from 'vitest';
import {
    TOOL_USE_RENDERERS,
    TOOL_RESULT_RENDERERS,
    renderToolUse,
    renderToolResult,
    getToolSummary,
} from './registry.js';

const CORE_TOOL_USE = ['Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep', 'Task', 'TodoWrite', 'AskUserQuestion'];

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

    it('renderBashUse escapes HTML in command', () => {
        const html = renderToolUse({
            name: 'Bash',
            input: { command: '<script>alert(1)</script>' },
        });
        expect(html).not.toContain('<script>');
        expect(html).toContain('&lt;script&gt;');
    });

    it('renderReadUse escapes file path in body', () => {
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
});

describe('getToolSummary', () => {
    it('formats Bash summary', () => {
        expect(getToolSummary('Bash', { command: 'ls -la' })).toMatch(/Bash:/);
        expect(getToolSummary('Bash', { command: 'ls -la' })).toContain('ls -la');
    });

    it('formats Read summary with escaped path', () => {
        expect(getToolSummary('Read', { file_path: 'a<b' })).toContain('&lt;b');
    });
});

describe('renderToolUse fallback', () => {
    it('uses JSON fallback for unknown tools', () => {
        const html = renderToolUse({
            name: 'WebFetch',
            input: { url: 'https://example.com' },
        });
        expect(html).toContain('tool-call');
        expect(html).toContain('example.com');
    });
});

describe('renderToolResult fallback', () => {
    it('renders summary-only for unknown result types', () => {
        const html = renderToolResult({ result_type: 'custom_type' });
        expect(html).toContain('Tool result (custom_type)');
        expect(html).toContain('tool-result');
    });
});
