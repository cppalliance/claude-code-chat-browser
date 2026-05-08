# Claude Code Chat Browser

Browse and export Claude Code chat history — Web GUI and CLI.

## Features

### Web GUI
- **Project dashboard** with card grid, aggregate stats, and staggered animations
- **Session viewer** with split layout (sidebar + message panel)
- **Full-text search** across all sessions
- **Syntax highlighting** for code blocks
- **Tool call rendering** — Bash, Read, Edit, Write, Glob, Grep, Task, TodoWrite, WebFetch, WebSearch, and more
- **Thinking blocks** — collapsible sections for Claude's reasoning
- **Dark/light theme** with Inter font
- **Responsive design** — mobile-friendly with hamburger sidebar
- **Toast notifications** with icon, progress bar, and close button
- **Confirm modals** with keyboard support (Enter/Escape) and backdrop blur
- **Top loading bar** (YouTube-style) during data fetches
- **Smooth transitions** — staggered card/message animations, crossfade content swaps
- **Scroll-to-top button** in bottom-right corner
- **Per-model badges** in session header
- **Bulk export** — download all sessions, incremental updates, or latest-day slice as a zip; if there is nothing to export, the API returns **422** with JSON body `{"error": "Nothing to export", "since": "<mode>"}` (the `since` field echoes your request: `"all"`, `"last"`, or `"incremental"`) instead of an empty zip

### CLI Export
- Standalone script to export all sessions to Markdown with YAML frontmatter
- Rich Markdown: token usage, tool calls, thinking blocks, model info, timestamps
- `--since last` — export every session that overlaps the **latest UTC calendar day** present in your history (default zip name: `claude-code-export-last-MM-DD-YYYY-MM-DD.zip` — the first `MM-DD` is that latest UTC day, and `YYYY-MM-DD` is the export date)
- `--since incremental` — export only sessions **new or changed since the last export** (file mtime + saved state)
- `--project` flag to export a subset of projects

## Quick Start

### Web GUI

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python app.py
# Open http://localhost:5000
```

Options:
```bash
python app.py --port 8080 --host 0.0.0.0
python app.py --base-dir /path/to/claude/projects
```

### CLI Export

```bash
# Activate venv first (see above), then:

# List all projects (first column is a friendly name; --project accepts that or the dir slug)
python scripts/export.py list

# Export all sessions as zip
python scripts/export.py

# Export to specific directory, no zip
python scripts/export.py --out ./exports --no-zip

# Latest calendar day (UTC): all sessions active on that day; zip pattern claude-code-export-last-MM-DD-YYYY-MM-DD.zip (e.g. claude-code-export-last-04-06-2026-05-08.zip — 04-06 = latest UTC day, 2026-05-08 = export date)
python scripts/export.py --since last

# Incremental (only new/updated sessions since last run, using export state)
python scripts/export.py --since incremental

# Export specific project only (substring on friendly name from list and/or dir name under ~/.claude/projects/)
python scripts/export.py --project boost-capy
```

The `--project` flag matches a **case-insensitive substring** of either the **Project** column from `list` (derived from the session working directory) or the internal directory name under `~/.claude/projects/` (for example `F--boost-capy` or `d--harbor-forge`). A substring like `boost-capy` matches `F--boost-capy`; you can also paste the friendly name shown in `list`.

## Data Source

Reads from `~/.claude/projects/` which contains JSONL session files created by Claude Code.

**Read-only**: Never writes to `~/.claude/`.

## Project Structure

```
claude-code-chat-browser/
├── app.py                    # Flask entry point (default port 5000)
├── api/
│   ├── projects.py           # Project listing & session counts
│   ├── sessions.py           # Session parsing & message delivery
│   ├── search.py             # Full-text search across sessions
│   └── export_api.py         # Bulk zip and per-session Markdown export
├── utils/
│   ├── session_path.py       # OS-aware path detection & project naming
│   ├── jsonl_parser.py       # JSONL session parser with tool result classification
│   └── md_exporter.py        # Markdown exporter with YAML frontmatter
├── scripts/
│   └── export.py             # Standalone CLI export tool
├── static/
│   ├── index.html            # SPA entry point (Inter font, minimal markup)
│   ├── css/style.css         # Dark/light theme, responsive, animations
│   └── js/app.js             # Hash-based routing, rendering, UI components
└── tests/
```

## Development

To run the test suite, install the dev requirements (Flask + pytest):

```bash
pip install -r requirements-dev.txt
pytest
```

`requirements.txt` carries only the runtime dep (Flask); `requirements-dev.txt` pulls it in via `-r` and adds pytest.

## Continuous integration

Every push and pull request runs **`pytest`** on **Ubuntu** (Python 3.12) via [`.github/workflows/ci.yml`](.github/workflows/ci.yml). A separate job verifies that `pip install -r requirements.txt` (production-only) is sufficient to import and boot the app.

## Exported Markdown Format

Each exported session includes:

- **YAML frontmatter**: title, timestamps, session_id, models, token counts, tool call breakdown, working directory, git branch, Claude Code version
- **Per-message metadata**: role, model, token usage (in/out/cache), timestamp
- **Thinking blocks**: Collapsible `<details>` sections
- **Tool calls**: Formatted by type (Bash commands, file reads/edits, glob/grep patterns, subagent tasks, todos, web fetches, plans)
- **System events**: Context compaction markers
