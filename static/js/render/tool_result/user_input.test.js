import { describe, expect, it } from 'vitest';
import { renderUserInputResult } from './user_input.js';
import { mountToolResult, expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderUserInputResult', () => {
    it('renders questions and answers', () => {
        const html = renderUserInputResult({
            result_type: 'user_input',
            questions: [{ question: 'Proceed?' }],
            answers: { proceed: 'yes' },
        });
        expect(html).toContain('User input received');
        expect(html).toContain('Proceed?');
        expect(html).toContain('yes');
        expect(html).toContain('Q:');
        expect(html).toContain('A:');
        expect(html).toContain('tool-result');
    });

    it('renders summary only when no questions or answers', () => {
        const html = renderUserInputResult({ result_type: 'user_input' });
        expect(html).toContain('User input received');
        expect(html).not.toContain('Q:');
        expect(html).not.toContain('A:');
    });

    it('escapes HTML in questions and answers', () => {
        const html = mountToolResult({
            result_type: 'user_input',
            questions: [{ question: XSS_SCRIPT }],
            answers: { key: '<bad>answer</bad>' },
        });
        expectNoRawHtml(html, [XSS_SCRIPT, '<bad>']);
        expect(html).toContain('&lt;bad&gt;');
    });
});
