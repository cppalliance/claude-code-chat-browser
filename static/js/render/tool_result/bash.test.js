import { describe, expect, it } from 'vitest';
import { renderBashResult } from './bash.js';
import { renderToolResult } from '../registry.js';
import { expectNoRawHtml, XSS_IMG } from '../test_helpers.js';

describe('renderBashResult', () => {
    it('renders success status with stdout', () => {
        const html = renderBashResult({
            result_type: 'bash',
            exit_code: 0,
            stdout: 'hello\nworld',
        });
        expect(html).toContain('Bash Result (success)');
        expect(html).toContain('hello');
        expect(html).toContain('stdout');
        expect(html).toContain('tool-result');
    });

    it('renders error status with stderr', () => {
        const html = renderBashResult({
            result_type: 'bash',
            exit_code: 1,
            is_error: true,
            stderr: 'command failed',
        });
        expect(html).toContain('error (exit 1)');
        expect(html).toContain('command failed');
        expect(html).toContain('stderr');
    });

    it('renders interrupted status', () => {
        const html = renderBashResult({ result_type: 'bash', interrupted: true });
        expect(html).toContain('Bash Result (interrupted)');
    });

    it('escapes HTML in stdout and stderr', () => {
        const html = renderToolResult({
            result_type: 'bash',
            exit_code: 0,
            stdout: XSS_IMG,
            stderr: '<script>x</script>',
        });
        expectNoRawHtml(html, [XSS_IMG, '<script>']);
        expect(html).toContain('&lt;img');
    });
});
