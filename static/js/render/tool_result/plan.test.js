import { describe, expect, it } from 'vitest';
import { renderPlanResult } from './plan.js';
import { mountToolResult, expectNoRawHtml, XSS_SCRIPT } from '../test_helpers.js';

describe('renderPlanResult', () => {
    it('renders plan file path in summary', () => {
        const html = renderPlanResult({
            result_type: 'plan',
            file_path: '.cursor/plans/sprint.md',
        });
        expect(html).toContain('Plan: .cursor/plans/sprint.md');
        expect(html).toContain('tool-result');
    });

    it('handles missing file path', () => {
        const html = renderPlanResult({ result_type: 'plan' });
        expect(html).toContain('Plan:');
        expect(html).not.toContain('undefined');
    });

    it('escapes HTML in file path via registry', () => {
        const html = mountToolResult({
            result_type: 'plan',
            file_path: XSS_SCRIPT,
        });
        expectNoRawHtml(html, [XSS_SCRIPT]);
    });
});
