# Architecture

**claude-code-chat-browser** reads JSONL session files written by Claude Code under `~/.claude/projects/` and serves them through a JSON HTTP API to a single-page web UI, with a parallel CLI export tool. The app is **read-only** toward `~/.claude/` — it never writes session data back to that tree.

## Component diagram

```text
                    ┌─────────────────────────────┐
                    │  ~/.claude/projects/      │
                    │    <project>/*.jsonl      │  (read-only data source)
                    └──────────────┬────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│ session_path    │    │ jsonl_parser        │    │ exclusion_rules  │
│ list_projects   │    │ session_peek        │    │ load + match     │
│ list_sessions   │    │ tool_dispatch       │    └────────┬─────────┘
│ safe_join       │    │ jsonl_helpers       │             │
└────────┬────────┘    └──────────┬──────────┘             │
         │                        │                        │
         └────────────┬───────────┴────────────────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │  api/                      │
         │  projects · sessions       │
         │  search · export_api       │
         │  error_codes               │
         └─────────────┬──────────────┘
                       │  Flask blueprints
                       ▼
         ┌────────────────────────────┐
         │  app.py — create_app()     │
         └─────────────┬──────────────┘
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
┌──────────────────┐          ┌──────────────────┐
│ static/          │          │ scripts/export.py │
│ index.html + js  │          │ (CLI, uses utils) │
└──────────────────┘          └──────────────────┘
```

## Layers

| Layer | Responsibility | Key modules |
|-------|----------------|-------------|
| **Data discovery** | Resolve `~/.claude/projects/`, list projects and sessions, prevent path traversal | `utils/session_path.py` |
| **Parsing** | JSONL → session dict (messages, metadata, tool rendering) | `utils/jsonl_parser.py`, `utils/tool_dispatch.py`, `utils/session_peek.py`, `utils/jsonl_helpers.py` |
| **Filtering** | Exclude sensitive sessions via rules file | `utils/exclusion_rules.py` |
| **Statistics** | Aggregates for API and exporters | `utils/session_stats.py` |
| **Export — Markdown** | Session → YAML-frontmatter Markdown | `utils/md_exporter.py` |
| **Export — JSON** | Session → JSON string for download | `utils/json_exporter.py` |
| **Export — state** | Incremental export checkpoints on disk | `utils/export_state_store.py`, `api/export_api.py` |
| **HTTP** | Routes, validation, error envelope | `api/*.py`, `api/error_codes.py` |
| **App factory** | Blueprint registration, rules loading, SPA static route | `app.py` |
| **Frontend** | Hash-routed UI, markdown render, shared state | `static/index.html`, `static/js/` |
| **CLI** | Same export semantics as bulk API, no HTTP | `scripts/export.py` |

## Data flow — typical UI session

1. Browser loads `GET /` → `static/index.html`.
2. SPA calls `GET /api/projects` → `list_projects()` + `quick_session_info()` for titled counts.
3. User opens a project → `GET /api/projects/<name>/sessions` → full `parse_session()` per file, exclusion filter, summary rows.
4. User opens a session → `GET /api/sessions/<project>/<id>` → full session JSON for the message panel.
5. Optional: `GET /api/sessions/.../stats` for sidebar metrics without loading all messages.
6. Search: `GET /api/search?q=...` scans all projects (brute force).
7. Export: `POST /api/export` or `GET /api/export/session/...` → Markdown/zip via exporters; state file updated on successful bulk export.

## Dispatch table

In `utils/tool_dispatch.py`, tool results are classified through `_parse_tool_result`, a **predicate-ordered dispatch table** (not a simple `if tool_name == ...` chain). **Order is load-bearing**: the first matching predicate wins. Tests in `tests/test_jsonl_parser.py` and `tests/test_real_session_fixtures.py` guard ordering regressions.

When adding a new tool renderer:

1. Add a `(predicate, builder)` pair to `_TOOL_RESULT_DISPATCH` in `utils/tool_dispatch.py`, preserving existing predicate order unless you also update fixtures and ordering tests (`tests/test_jsonl_parser.py`, `tests/test_real_session_fixtures.py`). Order is **not** “specific before generic” in general — the first match wins. `is_task_message_tool_result` is the intentional broad-before-narrow exception (`task_id` or `message` before retrieval/completed/async).
2. Add or extend a JSONL fixture under `tests/fixtures/` (especially for overlaps with existing predicates).
3. Run `pytest tests/test_jsonl_parser.py tests/test_real_session_fixtures.py -v`.

## Export state machine

Bulk export (`POST /api/export`) is stateful. State lives in `~/.claude-code-chat-browser/export-state.json` (see `EXPORT_STATE_FILE` in `utils/export_state_store.py`).

| `since` mode | Behavior |
|--------------|----------|
| `all` | Export all eligible sessions; update per-session mtimes in state |
| `last` | Export sessions active on the latest UTC calendar day in history |
| `incremental` | Export only sessions newer than last recorded mtime per id |

Writes are atomic (temp file + `os.replace`) under a lock from `_state_lock()`.

If zero sessions match, the API returns **`422`** with `EXPORT_NOTHING_TO_EXPORT` and echoes `since` — not an empty zip.

`GET /api/export/state` reads the same file without mutating it.

## Exclusion rules engine

At startup, `create_app()` loads rules from `--exclude-rules` or the default path into `app.config["EXCLUSION_RULES"]`. `is_session_excluded()` is applied on list, detail, search, and export paths so filtered sessions never appear in the UI or downloads.

## Frontend

The UI is a **hash-routed** SPA with ES modules under `static/js/`:

- `app.js` — routing and boot
- `projects.js`, `sessions.js`, `search.js`, `export.js` — route handlers
- `render/registry.js` — **tool dispatch registry** for session UI: `TOOL_USE_RENDERERS` and `TOOL_RESULT_RENDERERS` map tool name / `result_type` → render function (one module per type under `render/tool_use/` and `render/tool_result/`). Parallels backend `utils/tool_dispatch.py` (backend uses ordered predicates; frontend uses direct key lookup + fallback).
- `shared/markdown.js` — markdown + **DOMPurify** sanitization (do not render raw LLM HTML)
- `shared/state.js`, `shared/utils.js`, `shared/theme.js` — shared UI state and helpers

`sessions.js` keeps workspace/session orchestration and message bubbles; tool cards delegate to `render/registry.js`.

No bundler step — modern browsers load modules directly. Frontend unit tests use **vitest** + **jsdom** (`npm test`), including `static/js/render/registry.test.js` for registry wiring and renderer escaping.

## Content-Security-Policy

`create_app()` registers an `@app.after_request` hook that sets a `Content-Security-Policy` header on every Flask response. The policy is defined as `CSP_POLICY` in `app.py`:

| Directive | Sources | Notes |
|-----------|---------|-------|
| `default-src` | `'self'` | Fallback for unspecified fetch types |
| `script-src` | `'self'`, `https://cdnjs.cloudflare.com` | Self-hosted JS (e.g. `theme-init.js`, ES modules) plus SRI-pinned CDN scripts in `index.html` |
| `style-src` | `'self'`, `'unsafe-inline'`, `https://cdnjs.cloudflare.com` | `'unsafe-inline'` required for highlight.js theme inline styles **and** the app's own inline `style` attributes (e.g. hamburger `display:none` in `index.html`, layout tweaks in JS templates). Dropping highlight.js alone does not remove this need; nonces are the future tightening path |
| `img-src` | `'self'`, `data:` | Session images and data URLs |
| `connect-src` | `'self'` | API `fetch` calls to same origin |
| `font-src` | `'self'` | Local fonts only |
| `object-src` | `'none'` | Block plugins / `<object>` embeds (no plugin use in this app) |
| `form-action` | `'self'` | Restrict form submissions to same origin |
| `base-uri` | `'self'` | Restrict `<base>` tag injection |
| `frame-ancestors` | `'none'` | Prevent clickjacking via iframes |

**Keeping CDN sources in sync:** when adding or bumping a CDN asset in `static/index.html`, update both the SRI `integrity` hash and `CSP_POLICY` if the origin changes (today all CDN assets use `cdnjs.cloudflare.com`). Recompute SRI hashes against the live CDN payload when bumping highlight.js — `tests/test_hljs_theme_consistency.py` cross-checks `index.html`, `hljs-theme-init.js`, and `theme.js` stay in sync with each other (not the live CDN, which would be flaky in CI). Theme-init scripts were externalized to `static/js/theme-init.js` and `static/js/hljs-theme-init.js` so `script-src` does not require `'unsafe-inline'`. Navbar and route UI handlers use `addEventListener` instead of inline `onclick` attributes for the same reason.

## Continuous integration

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on push/PR:

- `prod-install-smoke` — production `requirements.txt` boots the app
- `pytest` — full Python suite with coverage gate on `api/` + `utils/`
- `integration-tests` — API integration subset + coverage artifact
- `js-tests` — `npm ci` + vitest

## What this codebase is not

- **Not multi-user** — no authn/authz; single local operator.
- **Not a writeback tool** — never modifies `~/.claude/`.
- **Not a search engine** — `/api/search` is O(sessions × messages); fine for personal history, not for large multi-tenant indexes.
- **Not a versioned public API** — no semver or OpenAPI contract yet; see [`docs/api-reference.md`](api-reference.md) as the human contract.

## Related documentation

- [API reference](api-reference.md)
- [Contributing](../CONTRIBUTING.md)
- [README](../README.md)
