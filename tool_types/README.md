# Tool type registration records

Each JSON file here is the **single source of truth** when adding a new Claude Code tool type.

## Workflow

1. Create or generate a record:

   ```bash
   python scripts/scaffold_tool_type.py --name my_tool --write-record-only
   ```

2. Edit the record: set `file_activity`, `result.predicate_keys`, TypedDict fields, and overlap metadata.

3. Run the generator:

   ```bash
   python scripts/scaffold_tool_type.py --record tool_types/my_tool.json
   ```

4. Complete the emitted TODO stubs (builder field mapping, render HTML), then run:

   ```bash
   pytest tests/test_tool_dispatch_sync.py tests/test_tool_dispatch_ordering.py -q
   ```

## Record schema

| Field | Description |
|-------|-------------|
| `name` | PascalCase tool use name (e.g. `ExampleTool`) |
| `file_activity` | `none`, `read`, `write`, `edit`, `bash`, or `web` |
| `use_input_keys` | Tool input keys shown in Markdown/JS stubs |
| `render_summary` | Human-readable label for exporters/renderers |
| `result` | Optional result-side registration (omit for use-only tools) |
| `result.dispatch_id` | `result_type` string (snake_case) |
| `result.typed_dict_fields` | `{name, type}` entries for the TypedDict |
| `result.predicate_keys` | Keys tested by the `is_*_tool_result` guard |
| `result.predicate_mode` | `all` (default) or `any` |
| `result.priority` | Overlap priority (`1` when beating another predicate) |
| `result.overlap_invariants` | Rows for `tests/test_tool_dispatch_ordering.py` |
| `result.overlap_invariants[].before_guard` | Optional explicit guard import (defaults to `is_<dispatch_id>_tool_result`) |
| `result.overlap_invariants[].after_guard` | Optional explicit guard import when dispatch id does not match guard naming |

See `models/tool_type_registry.py` for the authoritative dataclasses.
