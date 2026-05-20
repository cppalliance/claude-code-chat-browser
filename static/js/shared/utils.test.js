import { describe, it, expect } from 'vitest';
import { esc, truncate, formatTs, formatDate, formatSize } from './utils.js';

describe('esc', () => {
    it('escapes HTML special characters', () => {
        expect(esc('<script>"x"</script>')).toBe(
            '&lt;script&gt;&quot;x&quot;&lt;/script&gt;'
        );
    });

    it('returns empty string for falsy input', () => {
        expect(esc('')).toBe('');
        expect(esc(null)).toBe('');
    });
});

describe('truncate', () => {
    it('does not exceed max length', () => {
        expect(truncate('hello world', 5)).toBe('hello...');
    });

    it('returns short strings unchanged', () => {
        expect(truncate('hi', 10)).toBe('hi');
    });
});

describe('formatTs', () => {
    it('returns a formatted string for valid ISO date', () => {
        const out = formatTs('2026-05-19T10:00:00Z');
        expect(out).toMatch(/2026/);
        expect(out).toMatch(/05\/19\/2026/);
    });
});

describe('formatDate', () => {
    it('returns MM/DD/YYYY for valid ISO date', () => {
        expect(formatDate('2026-05-19T10:00:00Z')).toBe('05/19/2026');
    });
});

describe('formatSize', () => {
    it('formats bytes and kilobytes', () => {
        expect(formatSize(512)).toBe('512 B');
        expect(formatSize(2048)).toBe('2.0 KB');
    });
});
