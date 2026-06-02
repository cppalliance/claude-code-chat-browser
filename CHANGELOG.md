# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-06-02

### Added

- `__version__` in `app.py` for release tracking
- Startup guard refusing `--debug` with a non-loopback `--host`
- [Deprecation policy](docs/deprecation-policy.md) for API and JSON field changes
- API field **stability** tables in `docs/api-reference.md` (stable / experimental / deprecated)

### Changed

- README notes that the server enforces the debug + host safety rule at startup

### Deprecated

- `export_count` on `GET /api/export/state` (documented only; still returned). Use `last_export_session_count`. Removal planned in a follow-up release per [deprecation policy](docs/deprecation-policy.md).

[0.1.0]: https://github.com/cppalliance/claude-code-chat-browser/releases/tag/v0.1.0
