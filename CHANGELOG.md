# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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

[Unreleased]: https://github.com/cppalliance/claude-code-chat-browser/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cppalliance/claude-code-chat-browser/commits/v0.1.0
