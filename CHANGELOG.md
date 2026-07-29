# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] - 2026-07-30

### Added

- `docs/architecture.md` (#138): FTS5 search-index lock order, threading model, and forbidden nesting rules
- `tests/test_search_index_concurrency.py` (#139): concurrent rebuild and query, background refresh under load, lock-order assertions, `index_locked` live-scan fallback
- Dual-path parity oracles (#140): `tests/test_dual_path_parity_oracle.py` and `static/js/render/tool_result/dual_path_parity_oracle.test.js` run the same XSS payload through Python (`utils/md_exporter.py`, `utils/tool_dispatch.py`) and JS `renderToolResult`; malformed-input cases for truncated JSONL, broken parent UUIDs, and NUL bytes

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
