# Security Policy

## Supported Versions

This project is pre-release. Security fixes are applied to the **latest `master` branch only** (currently `0.1.0.dev0`).

| Version        | Supported |
| -------------- | --------- |
| latest `master`| Yes       |
| older commits  | No        |

## Reporting a Vulnerability

**Please do not open public GitHub issues for security vulnerabilities.**

Report vulnerabilities privately via [GitHub Security Advisories](https://github.com/cppalliance/claude-code-chat-browser/security/advisories/new). Private vulnerability reporting must be enabled on the repository (Settings → Security → Private vulnerability reporting). If you cannot use that form, contact the repository maintainers through an existing private channel.

## Response Timeline

| Stage | Target |
| ----- | ------ |
| Acknowledgment | Within **72 hours** of a valid report |
| Initial assessment | Within **7 days** |
| Fix for confirmed issues | Target **14 days** for issues affecting the default local-only deployment |

Timelines may extend for complex issues; we will keep reporters informed.

## Scope

### In scope

Security issues in this repository that affect users of the default local setup:

- **Path traversal** — session and export paths resolved via `safe_join` in `utils/session_path.py`
- **Cross-site scripting (XSS)** — rendered session HTML in `static/js/` (mitigated by DOMPurify + SRI in `static/index.html`)
- **Export integrity** — bulk zip and per-session export in `api/export_api.py` and `utils/export_engine.py`
- **Local file boundaries** — read-only access to `~/.claude/projects/`; writes limited to export output and app state
- **Debug-mode exposure** — Flask/Werkzeug debugger when `--debug` is combined with a non-loopback `--host` (blocked at startup in `app.py`)
- **Information disclosure** — API error responses scrub internal exception details (see `api/error_codes.py`)

### Out of scope

- **Intentional network-facing deployment** — this tool is designed for local browsing on loopback; exposing it on untrusted networks is not a supported configuration
- **Upstream Claude Code JSONL format bugs** — malformed or hostile data from Claude Code itself (we harden parsing but do not guarantee full isolation from arbitrary JSONL)
- **Third-party CDN availability** — DOMPurify is loaded from cdnjs with SRI; CDN compromise is an infrastructure concern outside this repo

## Existing Controls (reference)

| Control | Location |
| ------- | -------- |
| Path guard (`safe_join`) | `utils/session_path.py` |
| HTML sanitization (DOMPurify) | `static/js/shared/markdown.js`, `static/index.html` |
| Error response scrubbing | `api/error_codes.py`, session card handling in `api/projects.py` |
| Debug + non-loopback host guard | `app.py` (`validate_startup_cli`) |
