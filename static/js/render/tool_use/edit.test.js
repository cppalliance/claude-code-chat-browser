import { describe, expect, it } from 'vitest';
import { renderEditUse } from './edit.js';

describe('renderEditUse', () => {
    it('renders file path and old/new strings', () => {
        const html = renderEditUse({
            name: 'Edit',
            input: {
                file_path: 'src/app.js',
                old_string: 'const x = 1;',
                new_string: 'const x = 2;',
            },
        });
        expect(html).toContain('src/app.js');
        expect(html).toContain('const x = 1;');
        expect(html).toContain('const x = 2;');
        expect(html).toContain('tool-call');
    });

    it('escapes HTML in edit strings', () => {
        const html = renderEditUse({
            name: 'Edit',
            input: {
                file_path: 'x.txt',
                old_string: '<bad>',
                new_string: '<worse>',
            },
        });
        expect(html).not.toContain('<bad>');
        expect(html).toContain('&lt;bad&gt;');
        expect(html).not.toContain('<worse>');
        expect(html).toContain('&lt;worse&gt;');
    });
});
