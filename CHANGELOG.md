# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] - 2026-07-30

### Added

- `KNOWN_TOOL_TYPES` registry in `utils/tool_dispatch.py`; sync test keeps dispatch, file activity, Markdown export, and frontend renderers in step (#104)
- `static/tool_types.json` generated from the registry and loaded at SPA boot; warns in the console when renderers drift; unknown tools show their type name and JSON payload (#105)
- `GET /api/schema-report` and an amber banner on the session list when upstream JSONL fields appear or go missing (#108)
- Disk summary cache at `~/.claude-code-chat-browser/session_summary_cache.sqlite` plus a display-name cache so project and session lists load faster after restart (#111)
- FTS5 search index in `utils/search_index.py` with background rebuild; `/api/search` hits the index first and falls back to live scan; default window is 30 days (`all_history`, `since_days` for wider ranges) (#120)
- `/api/search` returns proper error codes for empty queries, overlong queries, bad `since_days`, and locked indexes; search page gets an all-history checkbox, a 50-result cap warning, snippet highlighting, and separate empty vs error UI (#121)
- Lock order and threading model for the search index in `docs/architecture.md` (#138)
- `tests/test_search_index_concurrency.py` for rebuild/query concurrency and lock-order checks (#139)
- Python and Vitest parity oracles in `tests/test_dual_path_parity_oracle.py` and `static/js/render/tool_result/dual_path_parity_oracle.test.js` (#140)

### Changed

- Session, stats, and export routes share `api/_session_handlers.py` and one `SESSION_LOAD_ERRORS` tuple (#125)
- Tool result dispatch picks winners by explicit priority instead of tuple order (`plan` over `file_write`, `task_message` over narrower task shapes) (#127)
- CLI bulk export prints the same `ErrorCode` values and messages as the HTTP API (#134)

### Fixed

- YAML frontmatter in Markdown export now quotes values that contain colons, `#`, tabs, newlines, or boolean literals; `models_used` and `service_tiers` export as sequences (#107)
- `SEARCH_INDEX_UNAVAILABLE` (503) when the FTS index is locked and live scan also fails (#122)

## [0.1.0] - 2026-06-18

### Added

- `__version__` in `app.py` for release tracking (`0.1.0` — first tagged release)
- Startup guard refusing `--debug` with a non-loopback `--host` (including bracketed IPv6 loopback such as `[::1]`)
- [Deprecation policy](docs/deprecation-policy.md) for API and JSON field changes
- API field **stability** tables in `docs/api-reference.md` (stable / experimental / deprecated)
- Vitest coverage for router, page modules, and tool renderers (`static/js/`)
- `Content-Security-Policy` header on all Flask responses; theme-init IIFE externalized to `static/js/theme-init.js`
- `RoleLiteral` narrowing for `MessageDict.role` with unknown-role fallback
- Mtime-invalidated LRU `session_cache` shared across session, stats, search, projects, and export APIs
- CI benchmark regression gate with populated `benchmarks/baselines.json` (fails on >20% mean regression)

### Changed

- README notes that the server enforces the debug + host safety rule at startup
- `utils/jsonl_parser.__all__` trimmed to public API symbols only (`parse_session`, `quick_session_info`)

### Removed

- `export_count` on `GET /api/export/state` — use `last_export_session_count` (deprecated in PR #60; removed before `v0.1.0` per [deprecation policy](docs/deprecation-policy.md) bundled SPA path; SPA updated in same release cut)

[Unreleased]: https://github.com/cppalliance/claude-code-chat-browser/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/cppalliance/claude-code-chat-browser/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/cppalliance/claude-code-chat-browser/commits/v0.1.0
