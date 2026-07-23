"""Dual-path Python/JS parity + malformed-input oracle tests.

Part A — golden-parity test:
    Feed an adversarial ``tool_result`` through the Python md-exporter path and
    assert the payload is neutralised inside a Markdown code fence.  The
    companion JS assertions live in
    ``static/js/render/tool_result/dual_path_parity_oracle.test.js`` and use the
    same adversarial blob through ``renderToolResult`` (the real JS dispatch
    path).

Part B — malformed-input oracle tests:
    Each scenario must produce a **specific, distinguishable degraded result** —
    not a silent empty and not an unhandled exception.

Oracle discipline (test-review C3/C8/C9):
    Every assertion checks the real observable outcome, never merely that
    parsing did not raise.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from utils.jsonl_parser import parse_session
from utils.md_exporter import _render_tool_result
from utils.tool_dispatch import _parse_tool_result

# ---------------------------------------------------------------------------
# Shared adversarial payload
# Both the Python and JS test files use this same vector so the two suites
# cover the same adversarial surface.
# ---------------------------------------------------------------------------

ADVERSARIAL_PAYLOAD: str = "<img src=x onerror=alert(1)>"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, lines: list[str]) -> str:
    """Write JSONL lines to *path*, return str path for parse_session."""
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _user_entry(uuid: str, text: str = "hello", parent_uuid: str | None = None) -> str:
    entry: dict[str, object] = {
        "type": "user",
        "uuid": uuid,
        "timestamp": "2026-01-01T00:00:00Z",
        "message": {"content": [{"type": "text", "text": text}]},
    }
    if parent_uuid is not None:
        entry["parentUuid"] = parent_uuid
    return json.dumps(entry)


def _assistant_entry(uuid: str, parent_uuid: str, text: str = "hi") -> str:
    return json.dumps(
        {
            "type": "assistant",
            "uuid": uuid,
            "parentUuid": parent_uuid,
            "timestamp": "2026-01-01T00:00:01Z",
            "message": {
                "model": "claude-test",
                "content": [{"type": "text", "text": text}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        }
    )


# ===========================================================================
# Part A — Golden-parity test (Python md-exporter path)
# ===========================================================================


def test_adversarial_bash_blob_dispatches_to_bash() -> None:
    """The adversarial bash blob classifies as result_type 'bash'.

    This drives the real ``_parse_tool_result`` dispatch path; a registry miss
    would produce result_type='unknown' and the assertion would fail.
    """
    tr: dict[str, object] = {
        "stdout": ADVERSARIAL_PAYLOAD,
        "exitCode": 0,
        "stderr": "",
        "interrupted": False,
        "is_error": False,
    }
    parsed = _parse_tool_result(tr)

    assert parsed is not None
    assert parsed["result_type"] == "bash", (
        f"expected result_type='bash', got {parsed['result_type']!r}; "
        "dispatch registry path must classify the blob correctly"
    )
    # stdout preserved through dispatch (not dropped)
    assert parsed["stdout"] == ADVERSARIAL_PAYLOAD


def test_adversarial_bash_result_python_path_wraps_in_code_fence() -> None:
    """Part A oracle: Python md-exporter wraps adversarial stdout in a Markdown
    code fence, neutralising the XSS vector as inert literal text.

    Negative control: if the code fence were removed from ``_render_tool_result``
    (renderer regressed to raw prose), ``opening_fence`` below would be None and
    the assertion would fail — a diverging renderer cannot pass this test.
    """
    tr: dict[str, object] = {
        "stdout": ADVERSARIAL_PAYLOAD,
        "exitCode": 0,
        "stderr": "",
        "interrupted": False,
        "is_error": False,
    }
    parsed = _parse_tool_result(tr)
    assert parsed is not None

    md = _render_tool_result(parsed)

    # Content must not be silently dropped
    assert ADVERSARIAL_PAYLOAD in md, (
        "adversarial payload must appear in Markdown output; it was silently dropped"
    )

    # The payload must sit inside a code fence, not in bare Markdown prose.
    # (Code fences render as <pre><code>…</code></pre>, which browsers display
    # as literal text and cannot execute as HTML.)
    lines = md.splitlines()
    fence_indices = [i for i, ln in enumerate(lines) if ln.strip().startswith("```")]
    payload_indices = [i for i, ln in enumerate(lines) if ADVERSARIAL_PAYLOAD in ln]

    assert fence_indices, "at least one Markdown code fence marker must be present"
    assert payload_indices, "adversarial payload must appear in at least one output line"

    payload_idx = payload_indices[0]
    opening_fence = next((i for i in fence_indices if i < payload_idx), None)
    closing_fence = next((i for i in fence_indices if i > payload_idx), None)

    assert opening_fence is not None, (
        f"no opening code fence before payload at line {payload_idx}; "
        "payload is exposed in bare Markdown prose — Python renderer diverged"
    )
    assert closing_fence is not None, (
        f"no closing code fence after payload at line {payload_idx}; "
        "code fence is unclosed — Python renderer diverged"
    )


# ===========================================================================
# Part B — Malformed-input oracle tests
# ===========================================================================


def test_truncated_final_line_returns_partial_parse(tmp_path: Path) -> None:
    """Truncated final line → earlier valid messages are returned, not a silent empty.

    Oracle: exactly 2 messages are parsed (the truncated line produces a
    JSONDecodeError and is silently skipped).  The result is distinguishable
    from both empty (0 messages, which would indicate catastrophic loss) and
    full success (3 messages, which would require parsing the truncated line).
    """
    line1 = _user_entry("u1")
    line2 = _assistant_entry("a1", parent_uuid="u1")
    # Simulate a truncated write: JSON object cut mid-serialisation
    full_line3 = _user_entry("u2", parent_uuid="a1")
    truncated = full_line3[: max(1, len(full_line3) // 2)]

    path = _write_jsonl(tmp_path / "truncated.jsonl", [line1, line2, truncated])
    session = parse_session(path)

    # Oracle: exactly 2 messages (truncated line dropped, prior messages intact)
    assert len(session["messages"]) == 2, (
        f"expected 2 messages (valid lines preserved, truncated line skipped), "
        f"got {len(session['messages'])}; "
        "a silent-empty regression would produce 0, a mis-parse would produce 1 or 3"
    )
    assert session["messages"][0]["role"] == "user"
    assert session["messages"][1]["role"] == "assistant"


def test_broken_parent_uuid_chain_stored_verbatim(tmp_path: Path) -> None:
    """Broken parentUuid → all messages parsed; broken pointer stored verbatim.

    The parser does not cross-reference parentUuid against known UUIDs; it stores
    the raw value and lets downstream tree traversal detect the break.

    Oracle: the assistant message's ``parent_uuid`` equals the non-existent UUID
    (not None, not the correct predecessor "u1").  Distinguishable from a
    well-formed chain where the value would be "u1".
    """
    DEAD_UUID = "00000000-dead-dead-dead-000000000000"

    line1 = _user_entry("u1")
    # assistant claims to descend from a UUID that never appeared in this file
    line2 = _assistant_entry("a1", parent_uuid=DEAD_UUID)

    path = _write_jsonl(tmp_path / "broken_chain.jsonl", [line1, line2])
    session = parse_session(path)

    # Both messages are present (no crash, no silent drop)
    assert len(session["messages"]) == 2, (
        f"expected 2 messages, got {len(session['messages'])}; "
        "broken parentUuid must not cause messages to be dropped"
    )

    assistant_msg = session["messages"][1]
    assert assistant_msg["role"] == "assistant"

    # Oracle: the broken pointer is stored as-is — not silenced to None or corrected
    assert assistant_msg["parent_uuid"] == DEAD_UUID, (
        f"expected broken UUID {DEAD_UUID!r}, got {assistant_msg['parent_uuid']!r}; "
        "parser must store the verbatim parentUuid value, not correct or silence it"
    )
    # Explicitly distinguishable from a well-formed chain
    assert assistant_msg["parent_uuid"] != "u1", (
        "parent_uuid must NOT be the correct predecessor UUID — this is the malformed case"
    )


def test_nul_bytes_in_line_dropped_valid_lines_recovered(tmp_path: Path) -> None:
    """NUL bytes embedded at the start and end of a JSONL line → that line is
    dropped; the subsequent valid line is parsed and returned.

    The parser opens with ``errors='replace'``, so NUL bytes survive to
    ``json.loads``, which rejects the leading NUL and raises JSONDecodeError.
    The next valid line is still processed.

    Oracle: exactly 1 message is recovered and its ``text`` equals the string
    from the valid line.  Not a silent empty (which would be 0 messages).
    """
    nul_line = b'\x00{"type":"user","uuid":"bad","message":{"content":[{"type":"text","text":"gone"}]}}\x00'
    valid_line = _user_entry("u-recovered", text="recovered-after-nul")

    path = tmp_path / "nuls.jsonl"
    path.write_bytes(nul_line + b"\n" + valid_line.encode("utf-8") + b"\n")

    session = parse_session(str(path))

    # Oracle: exactly 1 message (NUL-byte line dropped, valid line recovered)
    assert len(session["messages"]) == 1, (
        f"expected 1 message (NUL-line dropped, valid line recovered), "
        f"got {len(session['messages'])}; "
        "a silent-empty regression would produce 0"
    )
    assert session["messages"][0]["role"] == "user"
    # Specific oracle: text is from the valid line, not garbled NUL content
    assert session["messages"][0].get("text") == "recovered-after-nul", (
        f"expected text 'recovered-after-nul', got {session['messages'][0].get('text')!r}; "
        "the recovered message must carry the valid line's content"
    )


def test_tool_result_with_no_matching_tool_use_yields_specific_result_type(
    tmp_path: Path,
) -> None:
    """A user entry with a bash toolUseResult but no matching assistant tool_use
    → the message is parsed and ``tool_result_parsed`` carries result_type='bash'.

    This is the malformed case: in a well-formed session the user tool_result
    entry is preceded by an assistant entry with a matching tool_use id.  Here
    there is no such assistant entry at all.  The parser must still dispatch the
    blob and store the result — it must not silently set tool_result_parsed=None.

    Oracle: ``tool_result_parsed["result_type"] == "bash"`` and ``stdout``
    matches the input.  The message's ``slug`` is stored verbatim.
    Distinguishable from a missing tool_result (where tool_result_parsed
    would be None) and from an unknown dispatch (result_type='unknown').
    """
    bash_tr: dict[str, object] = {
        "stdout": "orphaned output",
        "exitCode": 0,
        "stderr": "",
        "interrupted": False,
        "is_error": False,
    }
    entry: dict[str, object] = {
        "type": "user",
        "uuid": "u-orphan",
        "parentUuid": "a-nonexistent",
        "timestamp": "2026-01-01T00:00:00Z",
        "slug": "orphaned-slug",
        "toolUseResult": bash_tr,
        "message": {"content": []},
    }

    path = _write_jsonl(tmp_path / "orphan_tr.jsonl", [json.dumps(entry)])
    session = parse_session(path)

    # Not a silent empty — exactly 1 message returned
    assert len(session["messages"]) == 1, (
        f"expected 1 message, got {len(session['messages'])}; "
        "orphaned tool_result must not cause the message to be silently dropped"
    )
    msg = session["messages"][0]
    assert msg["role"] == "user"

    # tool_result_parsed must be populated with the correct specific type
    trp = msg.get("tool_result_parsed")
    assert trp is not None, (
        "tool_result_parsed must not be None when toolUseResult is present; "
        "orphaned blob must still be dispatched through the real registry path"
    )
    assert trp["result_type"] == "bash", (
        f"expected result_type='bash' for bash blob, got {trp['result_type']!r}; "
        "distinguishable from result_type='unknown' (dispatch miss)"
    )
    assert trp.get("stdout") == "orphaned output", (
        f"expected stdout='orphaned output', got {trp.get('stdout')!r}; "
        "stdout must be preserved even without a matching tool_use"
    )
    # slug stored on the message (not on tool_result_parsed)
    assert msg.get("slug") == "orphaned-slug", (
        "slug must be stored verbatim on the user message"
    )
