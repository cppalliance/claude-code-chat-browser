# API Reference

HTTP API for **claude-code-chat-browser**. All `/api/*` routes return JSON unless noted. The bundled SPA at `GET /` is the primary client; these endpoints are also suitable for scripts and integrations on the same machine.

**Base URL (default):** `http://127.0.0.1:5000`

**Source of truth for error codes:** [`api/error_codes.py`](../api/error_codes.py)

---

## Authentication

None. The server binds to `127.0.0.1` by default and reads `~/.claude/projects/` as the local user. Do not expose it on a public network without adding authentication — there is no per-user authorization model.

---

## Error envelope

Every `4xx` and `5xx` response from `/api/*` uses this shape:

```json
{
  "error": "Human-readable message",
  "code": "MACHINE_READABLE_CODE"
}
```

Extra fields may appear for specific codes (for example `since` on invalid bulk-export mode).

| Field | Stability | Notes |
|-------|-----------|-------|
| `code` | Stable | `UPPER_SNAKE_CASE` string from `ErrorCode` enum |
| `error` | May be reworded | Kept for SPA compatibility |
| HTTP status | Stable per code | Use `code` + status together |

### Error code catalog

| `code` | HTTP | Routes | Meaning |
|--------|------|--------|---------|
| `SEARCH_INVALID_LIMIT` | 400 | `GET /api/search` | Query param `limit` is not a positive integer |
| `INVALID_PATH` | 400 | Session, stats, export session | Path traversal or rejected URL segment |
| `SESSION_NOT_FOUND` | 404 | Session, stats, export session | File missing on disk or session excluded by rules |
| `INVALID_REQUEST_BODY` | 400 | `POST /api/export` | Body is not a JSON object |
| `INVALID_SINCE_MODE` | 400 | `POST /api/export` | `since` is not `all`, `last`, or `incremental` |
| `PARSE_ERROR` | 500 | Session, stats, export session | JSONL file could not be parsed |
| `EXPORT_NOTHING_TO_EXPORT` | 422 | `POST /api/export` | No sessions matched the requested slice |
| `INTERNAL_ERROR` | 500 | `GET .../stats`, export session | Unexpected failure after parse (e.g. stats computation) |

---

## Exception-leakage policy

`5xx` responses never include exception class names, tracebacks, or file paths. The body is always the generic message documented per route. Full exceptions are logged server-side via `logger.exception`. See [`tests/test_error_propagation.py`](../tests/test_error_propagation.py) (issue #25).

---

## Exclusion rules

Sessions can be filtered by an exclusion rules file (default `~/.claude-code-chat-browser/exclusion-rules.txt`, overridable with `python app.py --exclude-rules PATH`). Excluded sessions:

- Are omitted from `GET /api/projects/<name>/sessions` and search results
- Return `404` with `SESSION_NOT_FOUND` on detail, stats, and per-session export routes

Grammar and matching: [`utils/exclusion_rules.py`](../utils/exclusion_rules.py).

---

## Endpoints

### `GET /`

**Source:** [`app.py`](../app.py)

Serves the single-page application shell (`static/index.html`). Hash-based client routing handles all UI navigation.

| | |
|--|--|
| **Response** | `200` — `text/html` |
| **Errors** | None |

```bash
curl -s http://127.0.0.1:5000/ -o /dev/null -w "%{http_code}\n"
```

---

### `GET /api/projects`

**Source:** [`api/projects.py`](../api/projects.py)

Lists every project directory under the Claude projects root that contains at least one `.jsonl` session file. Counts and `last_modified` reflect **titled** sessions only (via `quick_session_info` peek, not full parse).

#### Query parameters

None.

#### Response — `200 OK`

`application/json` — array of project objects:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Directory name under `~/.claude/projects/` (e.g. `F--boost-capy`) |
| `path` | string | Absolute path to project directory |
| `display_name` | string | Friendly name derived from session `cwd` when available |
| `session_count` | integer | Count of titled sessions (updated in handler) |
| `last_modified` | string (ISO 8601) | Latest message timestamp across titled sessions |

```json
[
  {
    "name": "F--boost-capy",
    "path": "/home/user/.claude/projects/F--boost-capy",
    "display_name": "Boost-capy",
    "session_count": 12,
    "last_modified": "2026-05-20T22:14:03+00:00"
  }
]
```

Empty projects root → `[]`.

#### Errors

None.

```bash
curl -s http://127.0.0.1:5000/api/projects | jq '.[0]'
```

---

### `GET /api/projects/<project_name>/sessions`

**Source:** [`api/projects.py`](../api/projects.py)

Lists sessions in one project with summary fields for the workspace sidebar. Skips untitled sessions and sessions matched by exclusion rules.

#### Path parameters

| Name | Type | Description |
|------|------|-------------|
| `project_name` | string | Project directory name; must not contain `..` |

#### Response — `200 OK`

`application/json` — array of session row objects:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Session id (filename without `.jsonl`) |
| `path` | string | Absolute path to JSONL file |
| `size_bytes` | integer | File size |
| `modified` | number | File mtime (epoch seconds) |
| `title` | string | Parsed session title |
| `models` | string[] | Models used in session |
| `tokens` | integer | Sum of input + output tokens |
| `tool_calls` | integer | Total tool calls |
| `first_timestamp` | string \| null | First message timestamp |
| `last_timestamp` | string \| null | Last message timestamp |
| `error` | boolean | Optional; `true` if parse failed (card shows error state) |

#### Errors

| Status | `code` | When |
|--------|--------|------|
| 400 | — | Invalid `project_name` (path escape). **Body is `[]`**, not a structured error — documented behavior |

```bash
curl -s "http://127.0.0.1:5000/api/projects/F--boost-capy/sessions" | jq '.[0]'
```

---

### `GET /api/sessions/<project_name>/<session_id>`

**Source:** [`api/sessions.py`](../api/sessions.py)

Returns the full parsed session: title, metadata, and messages (including tool calls and thinking blocks).

#### Path parameters

| Name | Type | Description |
|------|------|-------------|
| `project_name` | string | Project directory name |
| `session_id` | string | JSONL basename without `.jsonl` extension |

#### Response — `200 OK`

`application/json` — session object:

| Top-level field | Type | Description |
|-----------------|------|-------------|
| `session_id` | string | Session identifier |
| `title` | string | Inferred title from first human message |
| `messages` | array | Ordered message objects (`role`, `text`/`content`, tool fields, etc.) |
| `metadata` | object | Tokens, models, timestamps, file activity, tool counts, `cwd`, `git_branch`, … |

See [`utils/jsonl_parser.py`](../utils/jsonl_parser.py) `parse_session()` for the full metadata shape.

#### Errors

| Status | `code` | When |
|--------|--------|------|
| 400 | `INVALID_PATH` | Path traversal in URL |
| 404 | `SESSION_NOT_FOUND` | File missing or session excluded |
| 500 | `PARSE_ERROR` | Malformed JSONL |

```bash
curl -s "http://127.0.0.1:5000/api/sessions/F--boost-capy/session_abc123" | jq '.title'
```

---

### `GET /api/sessions/<project_name>/<session_id>/stats`

**Source:** [`api/sessions.py`](../api/sessions.py)

Computed aggregates for one session without returning the message list.

#### Path parameters

Same as session detail.

#### Response — `200 OK`

`application/json` — stats object from [`utils/session_stats.py`](../utils/session_stats.py) `compute_stats()`:

| Field | Type | Description |
|-------|------|-------------|
| `files_touched` | object | `read`, `written`, `created`, `total_unique` file lists |
| `commands_run` | array | Bash commands with exit metadata |
| `urls_accessed` | string[] | Web fetch URLs |
| `conversation_turns` | integer | Human/assistant turn count |
| `wall_clock_seconds` | number \| null | Session duration |
| `wall_clock_display` | string \| null | Human-readable duration |
| `cost_estimate_usd` | number | Best-effort USD estimate from token usage |
| `tool_result_summary` | object | Aggregated tool result stats |
| `stop_reason_summary` | object | Stop reason counts |
| `entry_type_counts` | object | JSONL entry type counts |
| `sidechain_message_count` | integer | Sidechain entries |
| `api_error_count` | integer | API errors in session |
| `compaction_events` | array | Context compaction markers |

#### Errors

| Status | `code` | When |
|--------|--------|------|
| 400 | `INVALID_PATH` | Path traversal |
| 404 | `SESSION_NOT_FOUND` | File missing |
| 500 | `PARSE_ERROR` | JSONL malformed |
| 500 | `INTERNAL_ERROR` | `compute_stats` failed after successful parse |

```bash
curl -s "http://127.0.0.1:5000/api/sessions/F--boost-capy/session_abc123/stats" | jq '.cost_estimate_usd'
```

---

### `GET /api/search`

**Source:** [`api/search.py`](../api/search.py)

Case-insensitive substring search across all non-excluded messages in all projects. Linear scan — suitable for local history size, not indexed search.

#### Query parameters

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `q` | string | `""` | Search string; whitespace stripped; empty → `[]` |
| `limit` | integer | `50` | Max results; must be ≥ 1; **capped at 500** |

#### Response — `200 OK`

`application/json` — array of hit objects:

| Field | Type | Description |
|-------|------|-------------|
| `project` | string | Project `name` |
| `session_id` | string | Session id |
| `title` | string | Session title |
| `role` | string | Message role (`human`, `assistant`, …) |
| `timestamp` | string \| null | Message timestamp |
| `snippet` | string | ~160 chars around match |

#### Errors

| Status | `code` | When |
|--------|--------|------|
| 400 | `SEARCH_INVALID_LIMIT` | `limit` not a positive integer (e.g. `abc`, `0`, `1.5`) |

```bash
curl -s "http://127.0.0.1:5000/api/search?q=parser&limit=10" | jq '.[0]'
curl -s "http://127.0.0.1:5000/api/search?q=test&limit=abc"   # → 400
```

---

### `GET /api/export/state`

**Source:** [`api/export_api.py`](../api/export_api.py)

Read-only snapshot of bulk-export state persisted under `~/.claude-code-chat-browser/export-state.json`.

#### Response — `200 OK`

| Field | Type | Description |
|-------|------|-------------|
| `last_export_time` | string \| null | ISO timestamp of last completed bulk export |
| `last_export_session_count` | integer | Sessions in last bulk export run |
| `export_count` | integer | Same as `last_export_session_count` (alias for UI) |

```json
{
  "last_export_time": "2026-05-20T18:42:11.123456",
  "last_export_session_count": 17,
  "export_count": 17
}
```

#### Errors

None.

```bash
curl -s http://127.0.0.1:5000/api/export/state | jq
```

---

### `POST /api/export`

**Source:** [`api/export_api.py`](../api/export_api.py)

Bulk-export sessions as a zip of Markdown files (plus `manifest.jsonl`). Updates export state when at least one session is exported.

#### Request body

`application/json`

| Field | Type | Required | Values |
|-------|------|----------|--------|
| `since` | string | no (default `"all"`) | `all` — every non-excluded titled session; `last` — latest UTC activity day; `incremental` — new/changed since last export |

#### Response — `200 OK`

`application/zip` with `Content-Disposition: attachment`

Filename pattern:

| `since` | Example filename |
|---------|------------------|
| `all` | `claude-code-export-2026-05-21.zip` |
| `last` | `claude-code-export-last-05-21-2026-05-21.zip` |
| `incremental` | `claude-code-export-incremental-2026-05-21.zip` |

Zip contains Markdown per session and optional `manifest.jsonl` metadata.

#### Errors

| Status | `code` | When | Extra fields |
|--------|--------|------|--------------|
| 400 | `INVALID_REQUEST_BODY` | Body is not a JSON object | — |
| 400 | `INVALID_SINCE_MODE` | Invalid `since` value | `since` echoes rejected value |
| 422 | `EXPORT_NOTHING_TO_EXPORT` | Zero sessions matched | `since` echoes request mode |

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"since":"last"}' \
  -o export.zip \
  http://127.0.0.1:5000/api/export
```

---

### `GET /api/export/session/<project_name>/<session_id>`

**Source:** [`api/export_api.py`](../api/export_api.py)

Download one session as Markdown or JSON.

#### Path parameters

Same as session detail.

#### Query parameters

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `format` | string | `md` | `md` — Markdown attachment; `json` — JSON attachment |

#### Response — `200 OK`

| `format` | Content-Type | Disposition |
|----------|--------------|-------------|
| `md` (default) | `text/markdown` | `attachment; filename="<slug>.md"` |
| `json` | `application/json` | `attachment; filename="<slug>.json"` |

JSON body matches `GET /api/sessions/.../` session object shape.

#### Errors

| Status | `code` | When |
|--------|--------|------|
| 400 | `INVALID_PATH` | Path traversal |
| 404 | `SESSION_NOT_FOUND` | Missing or excluded |
| 500 | `PARSE_ERROR` | JSONL malformed |
| 500 | `INTERNAL_ERROR` | Stats/export pipeline failure |

```bash
curl -OJ "http://127.0.0.1:5000/api/export/session/F--boost-capy/session_abc123"
curl -OJ "http://127.0.0.1:5000/api/export/session/F--boost-capy/session_abc123?format=json"
```

---

## Related documentation

- [Architecture overview](architecture.md)
- [Contributing](../CONTRIBUTING.md)
- [README](../README.md) — CLI export and quick start
