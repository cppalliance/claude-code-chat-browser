"""
XSS sanitization regression tests (issue #295, Day 4).

Source-level checks that enforce the DOMPurify sanitization contract:

1. DOMPurify is loaded in static/index.html with SRI and crossorigin="anonymous".
2. renderMarkdown in static/js/shared/markdown.js wraps marked.parse output with
   DOMPurify.sanitize before returning (the single safe rendering path).
3. No other JS file under static/ calls marked.parse() directly — all must go
   through renderMarkdown().
4. No JS file under static/ assigns a raw marked.parse() call directly to innerHTML.

Run:
    pytest tests/test_xss_sanitization.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "static" / "index.html"
MARKDOWN_JS = REPO_ROOT / "static" / "js" / "shared" / "markdown.js"
STATIC_JS_DIR = REPO_ROOT / "static" / "js"

DOMPURIFY_CDN_URL = "https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.2.7/purify.min.js"
DOMPURIFY_SRI = "sha512-78KH17QLT5e55GJqP76vutp1D2iAoy06WcYBXB6iBCsmO6wWzx0Qdg8EDpm8mKXv68BcvHOyeeP4wxAL0twJGQ=="


def _all_js_files():
    """Return all .js files under static/js/, excluding node_modules."""
    return [
        p for p in STATIC_JS_DIR.rglob("*.js")
        if "node_modules" not in p.parts
    ]


class TestDomPurifyInHTML:

    def test_dompurify_cdn_url_present(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        assert DOMPURIFY_CDN_URL in html, (
            f"DOMPurify CDN URL not found in index.html. "
            f"Expected: {DOMPURIFY_CDN_URL}"
        )

    def test_dompurify_sri_hash_present(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        assert DOMPURIFY_SRI in html, (
            "DOMPurify SRI hash not found in index.html. "
            "Add integrity= attribute to the DOMPurify <script> tag (issue #295)."
        )

    def test_dompurify_crossorigin_anonymous(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        # Find the script tag that loads DOMPurify and check crossorigin attribute
        script_re = re.compile(
            r'<script\b[^>]*' + re.escape("dompurify") + r'[^>]*>',
            re.DOTALL | re.IGNORECASE,
        )
        m = script_re.search(html)
        assert m, "No <script> tag referencing dompurify found in index.html"
        tag = m.group(0)
        assert 'crossorigin="anonymous"' in tag, (
            f"DOMPurify <script> tag missing crossorigin=\"anonymous\": {tag!r}"
        )


class TestRenderMarkdownSanitizes:

    def test_render_markdown_calls_dompurify_sanitize(self):
        """renderMarkdown must pass marked.parse output through DOMPurify.sanitize."""
        src = MARKDOWN_JS.read_text(encoding="utf-8")
        # DOMPurify.sanitize must appear in the file
        assert "DOMPurify.sanitize(" in src, (
            "shared/markdown.js: renderMarkdown must call DOMPurify.sanitize() "
            "on the marked.parse output (issue #295)."
        )

    def test_render_markdown_wraps_marked_parse(self):
        """DOMPurify.sanitize must wrap the marked.parse call, not appear separately."""
        src = MARKDOWN_JS.read_text(encoding="utf-8")
        # Both calls must be present in the same file
        assert "marked.parse(" in src, (
            "shared/markdown.js: marked.parse() call not found — renderMarkdown "
            "should parse then sanitize."
        )
        # DOMPurify.sanitize must appear AFTER marked.parse in the source
        sanitize_pos = src.index("DOMPurify.sanitize(")
        parse_pos = src.index("marked.parse(")
        assert sanitize_pos > parse_pos or "DOMPurify.sanitize(marked.parse(" in src, (
            "shared/markdown.js: DOMPurify.sanitize should wrap marked.parse output."
        )

    def test_render_markdown_exported(self):
        src = MARKDOWN_JS.read_text(encoding="utf-8")
        assert "export function renderMarkdown" in src, (
            "shared/markdown.js must export renderMarkdown so route modules can import it."
        )


class TestNoDirectMarkedParseOutsideWrapper:

    def test_only_shared_markdown_calls_marked_parse(self):
        """No JS file other than shared/markdown.js may call marked.parse() directly."""
        violations = []
        for js_file in _all_js_files():
            if js_file == MARKDOWN_JS:
                continue
            src = js_file.read_text(encoding="utf-8")
            if "marked.parse(" in src:
                violations.append(str(js_file.relative_to(REPO_ROOT)))
        assert not violations, (
            "The following JS files call marked.parse() directly (issue #295). "
            "All markdown rendering must go through renderMarkdown() in "
            f"shared/markdown.js:\n  " + "\n  ".join(violations)
        )

    def test_no_raw_marked_parse_to_inner_html(self):
        """No JS file may assign a marked.parse() result directly to innerHTML."""
        # Pattern: innerHTML = ... marked.parse(...) without DOMPurify wrapping
        raw_assign_re = re.compile(r'innerHTML\s*[+]?=.*marked\.parse\s*\(', re.DOTALL)
        violations = []
        for js_file in _all_js_files():
            src = js_file.read_text(encoding="utf-8")
            if raw_assign_re.search(src):
                violations.append(str(js_file.relative_to(REPO_ROOT)))
        assert not violations, (
            "The following JS files assign marked.parse() output directly to innerHTML "
            "without DOMPurify (issue #295):\n  " + "\n  ".join(violations)
        )
