import { describe, expect, it } from 'vitest';
import { renderReadUse } from './read.js';
import { renderToolUse } from '../registry.js';
import { expectNoRawHtml, expectEscaped, XSS_SCRIPT } from '../test_helpers.js';

describe('renderReadUse', () => {
    it('renders file path in summary and body', () => {
        const html = renderReadUse({
            name: 'Read',
            input: { file_path: 'src/main.cpp' },
        });
        expect(html).toContain('src/main.cpp');
        expect(html).toContain('tool-call');
    });

    it('handles missing input gracefully', () => {
        const html = renderReadUse({ name: 'Read' });
        expect(html).toContain('Read:');
        expect(html).toContain('tool-call');
    });

    it('escapes HTML in file path', () => {
        const html = renderToolUse({
            name: 'Read',
            input: { file_path: XSS_SCRIPT },
        });
        expectNoRawHtml(html, [XSS_SCRIPT]);
        expectEscaped(html, '&lt;script&gt;');
    });
});
