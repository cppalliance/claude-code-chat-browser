import { describe, expect, it } from 'vitest';
import { renderAskUserQuestionUse } from './ask_user_question.js';
import { mountToolUse, expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderAskUserQuestionUse', () => {
    it('renders questions in the body', () => {
        const html = renderAskUserQuestionUse({
            name: 'AskUserQuestion',
            input: {
                questions: [
                    { question: 'Which option?' },
                    { question: 'Confirm proceed?' },
                ],
            },
        });
        expect(html).toContain('Which option?');
        expect(html).toContain('Confirm proceed?');
        expect(html).toContain('Q:');
        expect(html).toContain('tool-call');
    });

    it('handles empty questions list', () => {
        const html = renderAskUserQuestionUse({
            name: 'AskUserQuestion',
            input: { questions: [] },
        });
        expect(html).toContain('AskUserQuestion');
        expect(html).toContain('tool-call');
    });

    it('escapes HTML in question text', () => {
        const html = mountToolUse({
            name: 'AskUserQuestion',
            input: { questions: [{ question: XSS_SCRIPT }] },
        });
        expectNoRawHtml(html, [XSS_SCRIPT]);
        expect(html).toContain('&lt;script&gt;');
    });
});
