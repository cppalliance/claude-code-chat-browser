"""Regression test for highlight.js theme URL+hash drift between
static/index.html (initial load) and static/js/app.js (runtime swap).

Both files carry the dark-theme stylesheet URL and its SRI hash. On a
highlight.js version bump both must update together — if they drift, either
the initial load breaks (HTML stale, mismatched hash) or the runtime theme
swap breaks (JS stale). This test fails fast when they diverge so the
"MUST also swap the integrity attribute" comments in both files become a
checked invariant rather than a hope.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "static" / "index.html"
HLJS_THEME_INIT_JS = REPO_ROOT / "static" / "js" / "hljs-theme-init.js"
# HLJS_THEME_SHEETS was extracted to shared/theme.js (Day 4 module split).
# app.js re-exports it, but the canonical source is theme.js.
APP_JS = REPO_ROOT / "static" / "js" / "shared" / "theme.js"


def _link_attr(html: str, link_id: str, attr: str) -> str:
    """Return the value of `attr` on the <link> tag with id=`link_id`."""
    tag_re = re.compile(
        r'<link\b[^>]*\bid\s*=\s*"' + re.escape(link_id) + r'"[^>]*>',
        re.DOTALL,
    )
    m = tag_re.search(html)
    assert m, f'No <link id="{link_id}"> found in index.html'
    attr_m = re.search(re.escape(attr) + r'\s*=\s*"([^"]*)"', m.group(0))
    assert attr_m, f'<link id="{link_id}"> has no {attr!r} attribute'
    return attr_m.group(1)


def _js_theme_entry(js: str, theme: str) -> dict:
    """Return {'href': ..., 'integrity': ...} from HLJS_THEME_SHEETS.<theme>."""
    block = re.search(re.escape(theme) + r"\s*:\s*\{([^}]*)\}", js, re.DOTALL)
    assert block, f"HLJS_THEME_SHEETS.{theme} entry not found in app.js"
    body = block.group(1)
    out = {}
    for key in ("href", "integrity"):
        m = re.search(key + r"\s*:\s*['\"]([^'\"]+)['\"]", body)
        assert m, f"HLJS_THEME_SHEETS.{theme} has no {key!r} key"
        out[key] = m.group(1)
    return out


def _js_string_assignments(js: str, keys: tuple[str, ...]) -> dict[str, str]:
    """Return string literal assignments like ``link.href = '...'`` from classic JS."""
    out: dict[str, str] = {}
    for key in keys:
        m = re.search(
            r"link\." + re.escape(key) + r"\s*=\s*['\"]([^'\"]+)['\"]",
            js,
        )
        assert m, f"hljs-theme-init.js has no link.{key} assignment"
        out[key] = m.group(1)
    return out


def test_dark_theme_url_and_hash_match_between_html_and_js():
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    html_href = _link_attr(html, "hljs-theme", "href")
    html_integrity = _link_attr(html, "hljs-theme", "integrity")
    js_dark = _js_theme_entry(js, "dark")

    assert html_href == js_dark["href"], (
        "highlight.js theme URL drifted between index.html and app.js — "
        f"html={html_href!r}, app.js HLJS_THEME_SHEETS.dark={js_dark['href']!r}. "
        "On a version bump both must update together (issue #19)."
    )
    assert html_integrity == js_dark["integrity"], (
        "highlight.js theme SRI hash drifted between index.html and app.js — "
        f"html={html_integrity!r}, "
        f"app.js HLJS_THEME_SHEETS.dark={js_dark['integrity']!r}."
    )


def test_light_theme_url_and_hash_match_between_hljs_init_and_theme_js():
    init_js = HLJS_THEME_INIT_JS.read_text(encoding="utf-8")
    theme_js = APP_JS.read_text(encoding="utf-8")

    init = _js_string_assignments(init_js, ("integrity", "href"))
    js_light = _js_theme_entry(theme_js, "light")

    assert init["href"] == js_light["href"], (
        "highlight.js light theme URL drifted between hljs-theme-init.js and theme.js — "
        f"init={init['href']!r}, theme.js HLJS_THEME_SHEETS.light={js_light['href']!r}."
    )
    assert init["integrity"] == js_light["integrity"], (
        "highlight.js light theme SRI hash drifted between hljs-theme-init.js and theme.js — "
        f"init={init['integrity']!r}, "
        f"theme.js HLJS_THEME_SHEETS.light={js_light['integrity']!r}."
    )
