# Contributor onboarding

Welcome. This doc is the **fast path** for your first PR. It links the existing guides rather than repeating them — read it once, then bookmark the references below.

## Before you start

| Doc | What it covers |
|-----|----------------|
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Dev setup, code style, PR checklist, where to change each layer |
| [docs/architecture.md](architecture.md) | Data flow, export state machine, dispatch table, frontend layout |
| [docs/api-reference.md](api-reference.md) | HTTP routes, error codes, field stability |

## Suggested reading order

Work through these in order before touching unfamiliar code:

1. **[docs/architecture.md](architecture.md)** — component diagram, layers, and how JSONL becomes API + UI.
2. **[utils/jsonl_parser.py](../utils/jsonl_parser.py)** — session parsing entry point; tool results flow through `tool_dispatch`.
3. **[utils/tool_dispatch.py](../utils/tool_dispatch.py)** — priority-based `_TOOL_RESULT_DISPATCH` table; read the module docstring and [dispatch table notes](architecture.md#dispatch-table).
4. **Frontend SPA** — [`static/js/app.js`](../static/js/app.js) (routing), [`static/js/sessions.js`](../static/js/sessions.js) (message panel), [`static/js/render/registry.js`](../static/js/render/registry.js) (tool renderers).

For API or export changes, also skim [`api/error_codes.py`](../api/error_codes.py) and [`utils/md_exporter.py`](../utils/md_exporter.py).

## First PR walkthrough

### 1. Fork and clone

```powershell
# GitHub UI: fork cppalliance/claude-code-chat-browser to your account, then:
git clone https://github.com/<your-user>/claude-code-chat-browser.git
cd claude-code-chat-browser
git remote add upstream https://github.com/cppalliance/claude-code-chat-browser.git
```

On macOS/Linux, use the same `git clone` / `git remote add` commands in your shell.

### 2. Create a branch

Branch names follow `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, etc. (see [CONTRIBUTING.md](../CONTRIBUTING.md#branching-and-pull-requests)).

```bash
git fetch upstream
git checkout -b docs/my-first-change upstream/master
```

### 3. Development setup

Follow **[CONTRIBUTING.md — Development setup](../CONTRIBUTING.md#development-setup)** for your OS (Python 3.12 venv, `pip install -r requirements-dev.txt`, optional Node 20+ for JS).

Smoke-test the dev server:

```bash
python app.py --port 5000
# Open http://127.0.0.1:5000
```

### 4. Make a focused change

- One logical change per PR when possible.
- Match existing conventions (ruff, import order, `error_response()` for API errors) — see [Code style](../CONTRIBUTING.md#code-style-and-conventions).
- Add or update tests for behavior changes — see [Tests required](../CONTRIBUTING.md#tests-required-for-common-changes).

### 5. Run the full local gate

CI runs these on Ubuntu, Windows, and macOS. Run them locally before opening a PR:

```bash
# Lint + format (required)
ruff check .
ruff format --check .

# Type check (Ubuntu CI job; run locally before Python-heavy changes)
mypy -p api -p utils -p models -p scripts

# Security audit (production deps)
pip-audit -r requirements.txt

# Python tests (full suite)
pytest -q

# Integration subset (also run in CI)
pytest tests/test_api_integration.py -v

# Frontend — only if you changed static/js/
npm ci
npm test
```

Fix formatting with `ruff format .` when `ruff format --check` fails.

### 6. Push and open a PR

```bash
git push -u origin docs/my-first-change
```

Open a pull request against **`master`** on `cppalliance/claude-code-chat-browser`. Include:

- A short summary of **why** the change is needed.
- A **Test plan** checklist (what you ran locally).
- Links to any related issue (`Fixes #NNN` when applicable).

### 7. Review

[`.github/CODEOWNERS`](../.github/CODEOWNERS) auto-requests reviewers on new PRs. **Do not self-merge** — wait for at least one approval. Address review feedback in follow-up commits on the same branch.

## Good first issues

Browse open issues filtered by label:

- [**good first issue**](https://github.com/cppalliance/claude-code-chat-browser/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) — scoped for newcomers
- [**help wanted**](https://github.com/cppalliance/claude-code-chat-browser/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22) — maintainers welcome extra hands
- [**documentation**](https://github.com/cppalliance/claude-code-chat-browser/issues?q=is%3Aissue+is%3Aopen+label%3Adocumentation) — docs-only patches

Not sure which issue to pick? Comment on an issue or open a draft PR early for CI feedback — see [Getting help](../CONTRIBUTING.md#getting-help).

## Maintainer coverage (bus factor)

Recent commit history is concentrated on a small set of identities. If those maintainers are unavailable, review and release can stall.

**Mitigations in this repo:**

- **[`.github/CODEOWNERS`](../.github/CODEOWNERS)** — routes review requests so PRs do not rely on ad-hoc pings.
- **This onboarding path** — lowers the ramp for a second reviewer or contributor to run gates and ship safely.

If you are joining as a reviewer, read the [suggested reading order](#suggested-reading-order) and run the [full local gate](#5-run-the-full-local-gate) once on `master` before approving your first PR.
