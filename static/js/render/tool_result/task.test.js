import { describe, expect, it } from 'vitest';
import { renderTaskResult } from './task.js';
import { mountToolResult, expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderTaskResult', () => {
    it('renders completed task with duration and token stats', () => {
        const html = renderTaskResult({
            result_type: 'task',
            status: 'completed',
            total_duration_ms: 2500,
            total_tokens: 1500,
            total_tool_use_count: 3,
        });
        expect(html).toContain('Task completed');
        expect(html).toContain('2.5s');
        expect(html).toContain('1,500 tokens');
        expect(html).toContain('3 tool calls');
        expect(html).toContain('tool-result');
    });

    it('prefers retrieval status summary when set', () => {
        const html = renderTaskResult({
            result_type: 'task',
            retrieval_status: 'found',
            status: 'completed',
        });
        expect(html).toContain('Task retrieval: found');
        expect(html).not.toContain('Task completed');
    });

    it('prefers description summary when set', () => {
        const html = renderTaskResult({
            result_type: 'task',
            description: 'explore auth module',
        });
        expect(html).toContain('Task launched: explore auth module');
    });

    it('escapes HTML in description via registry', () => {
        const html = mountToolResult({
            result_type: 'task',
            description: XSS_SCRIPT,
        });
        expectNoRawHtml(html, [XSS_SCRIPT]);
    });
});
