# Contributing

Thanks for considering a patch. This repo is a small Flask app plus a hash-routed SPA and a CLI export script. Keep changes focused and tested.

## Development setup

### Prerequisites

- **Python 3.12** (matches CI)
- **Node 20+** (only if you change `static/js/` or run frontend unit tests)

### Bootstrap (Windows PowerShell)

```powershell
git clone https://github.com/cppalliance/claude-code-chat-browser.git
cd claude-code-chat-browser
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

### Bootstrap (macOS / Linux)

```bash
git clone https://github.com/cppalliance/claude-code-chat-browser.git
cd claude-code-chat-browser
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Run the dev server

```bash
python app.py --port 5000
# Open http://127.0.0.1:5000
```

Useful flags:

- `--base-dir PATH` — point at a different `projects/` tree (for tests or fixtures)
- `--exclude-rules PATH` — session exclusion rules file
- `--host 0.0.0.0` — listen on all interfaces (use only on trusted networks; never with `--debug`)
- `--debug` — Flask/Werkzeug debug mode (loopback hosts only; enforced when starting via `python app.py`, not `flask run` or WSGI). Extending the guard to `FLASK_DEBUG` / `flask run` is a planned follow-up.

## API and release policy

- [CHANGELOG.md](CHANGELOG.md) — user-visible changes per release
- [docs/deprecation-policy.md](docs/deprecation-policy.md) — how deprecated API fields are removed
- [docs/api-reference.md](docs/api-reference.md) — field **stability** (`stable` / `experimental` / `deprecated`)

When changing JSON response shapes, update the API reference stability column and CHANGELOG before removing fields.

## Running tests

### Python

```bash
pytest -q                              # full suite + coverage (see pyproject.toml)
pytest tests/test_api_integration.py -v
pytest tests/test_search.py -v
pytest tests/test_api_routes.py -v
pytest tests/test_error_codes.py -v
```

### JavaScript (vitest)

Only needed when editing `static/js/`:

```bash
npm ci
npm test
npm run test:coverage   # optional
```

`node_modules/` is gitignored — run `npm ci` after clone.

## Code style and conventions

| Area | Convention |
|------|------------|
| **API errors** | Use `error_response()` from [`api/error_codes.py`](api/error_codes.py). Do not call `jsonify({"error": ...})` without a `code` field. Add new members to `ErrorCode` and a row in `tests/test_error_codes.py`. |
| **Exception leakage** | `5xx` bodies are generic messages only. Log full tracebacks with `current_app.logger.exception(...)`. Never put `str(e)` or class names in HTTP JSON (issue #25). |
| **Path safety** | Use `safe_join()` from `utils/session_path.py` for any path built from URL segments. |
| **Imports** | stdlib → third-party → local, blank line between groups. |
| **Line length** | ~100 characters; no enforced formatter yet. |

## Tests required for common changes

| Change | Add or update |
|--------|----------------|
| New HTTP route | Happy + error path in `tests/test_api_routes.py` or `tests/test_api_integration.py` |
| New `ErrorCode` | Parametrized row in `tests/test_error_codes.py` |
| Search / limit validation | `tests/test_search.py` |
| New `_parse_tool_result` dispatch entry | Fixture + assertion in `tests/test_jsonl_parser.py` |
| CLI behavior | `tests/test_cli_e2e.py` (subprocess) or `tests/test_cli_args.py` (parser only) |
| Frontend shared module | `static/js/shared/*.test.js` (vitest) |
| Error response shape | `tests/test_error_propagation.py` regression |

## Branching and pull requests

- Default branch: **`master`**. Do not push directly to `master`.
- Branch names: `feat/<topic>`, `fix/<topic>`, `test/<topic>`, `chore/<topic>`, `docs/<topic>`.
- One logical change per PR when possible.
- PR checklist:
  - [ ] `pytest -q` green locally
  - [ ] `npm test` green if JS changed
  - [ ] CI jobs green (`pytest`, `integration-tests`, `js-tests`, `prod-install-smoke`)
  - [ ] PR description includes a **Test plan** section
  - [ ] API changes update [`docs/api-reference.md`](docs/api-reference.md) if behavior or errors change

## Where things live

| Task | Location |
|------|----------|
| Add HTTP route | `api/<area>.py`, register blueprint in [`app.py`](app.py) |
| Add stable error code | [`api/error_codes.py`](api/error_codes.py) |
| Parse JSONL / tool results | [`utils/jsonl_parser.py`](utils/jsonl_parser.py) — see [dispatch table notes](docs/architecture.md#dispatch-table) |
| Project/session discovery | [`utils/session_path.py`](utils/session_path.py) |
| Session statistics | [`utils/session_stats.py`](utils/session_stats.py) |
| Bulk / per-session export | [`api/export_api.py`](api/export_api.py), [`utils/md_exporter.py`](utils/md_exporter.py) |
| Export state on disk | [`utils/export_state_store.py`](utils/export_state_store.py) |
| Exclusion rules | [`utils/exclusion_rules.py`](utils/exclusion_rules.py) |
| CLI export | [`scripts/export.py`](scripts/export.py) |
| SPA shell + routing | [`static/index.html`](static/index.html), [`static/js/app.js`](static/js/app.js) |
| Shared frontend utilities | [`static/js/shared/`](static/js/shared/) |
| API documentation | [`docs/api-reference.md`](docs/api-reference.md) |
| Deprecation policy | [`docs/deprecation-policy.md`](docs/deprecation-policy.md) |
| Changelog | [`CHANGELOG.md`](CHANGELOG.md) |

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for data flow, export state machine, and component diagram.

## Getting help

Open an issue with a clear repro or propose a draft PR early for CI feedback.
