# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `__version__` in `app.py` for release tracking (`0.1.0.dev0` until the first `v0.1.0` git tag)
- Startup guard refusing `--debug` with a non-loopback `--host` (including bracketed IPv6 loopback such as `[::1]`)
- [Deprecation policy](docs/deprecation-policy.md) for API and JSON field changes
- API field **stability** tables in `docs/api-reference.md` (stable / experimental / deprecated)

### Changed

- README notes that the server enforces the debug + host safety rule at startup

### Deprecated

- `export_count` on `GET /api/export/state` (documented only; still returned). Use `last_export_session_count`. Removal planned in a follow-up release per [deprecation policy](docs/deprecation-policy.md).
