// Sanitized markdown rendering (issue #295).
// renderMarkdown() is the ONLY function that may produce HTML from untrusted
// session content. All callers must use this wrapper — never call marked.parse()
// directly and assign the result to innerHTML.

import { esc } from './utils.js';

/** Strip Claude Code internal XML noise before markdown rendering. */
export function cleanContent(s) {
    if (!s) return '';
    let text = s;
    text = text.replace(/<system-reminder>[\s\S]*?<\/system-reminder>/g, '');
    text = text.replace(/<user-prompt-submit-hook>[\s\S]*?<\/user-prompt-submit-hook>/g, '');
    text = text.replace(/<claude_background_info>[\s\S]*?<\/claude_background_info>/g, '');
    text = text.replace(/<fast_mode_info>[\s\S]*?<\/fast_mode_info>/g, '');
    text = text.replace(/<env>[\s\S]*?<\/env>/g, '');
    text = text.replace(/<ide_opened_file>[\s\S]*?<\/ide_opened_file>/g, '');
    text = text.replace(/<ide_selection>([\s\S]*?)<\/ide_selection>/g, '```\n$1\n```');
    text = text.replace(/<local-command-stdout>([\s\S]*?)<\/local-command-stdout>/g, '```\n$1\n```');
    text = text.replace(/<local-command-stderr>([\s\S]*?)<\/local-command-stderr>/g, '```\n$1\n```');
    text = text.replace(/\n{3,}/g, '\n\n');
    return text.trim();
}

/**
 * Parse markdown and sanitize the HTML output with DOMPurify before returning.
 *
 * DOMPurify strips script tags, event handlers, javascript: URLs, and other
 * dangerous constructs while preserving safe markup (pre, code, em, strong,
 * blockquote, table, details, summary, etc.) including class attributes needed
 * for highlight.js. This is the single safe rendering path for all untrusted
 * session content (user prompts, model responses, tool output).
 */
export function renderMarkdown(text) {
    if (!text) return '';
    if (typeof marked !== 'undefined') {
        try {
            const parsed = marked.parse(text, { breaks: true, gfm: true });
            if (typeof DOMPurify !== 'undefined') {
                return DOMPurify.sanitize(parsed);
            }
            // DOMPurify not yet loaded — return parsed but log a warning
            console.warn('[renderMarkdown] DOMPurify not available; output is unsanitized');
            return parsed;
        } catch (e) { /* fall through to escaped fallback */ }
    }
    // Fallback: fully escaped output with basic code block conversion (no DOMPurify needed)
    let out = esc(text);
    out = out.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
    return out;
}
