"""Tests for utils/export_state_store.load_export_state_from_disk validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from utils.export_state_store import (
    atomic_write_export_state,
    export_state_lock,
    load_export_state_from_disk,
)


def test_load_rejects_non_object_json(tmp_path: Path):
    p = tmp_path / "export_state.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert load_export_state_from_disk(str(p)) == {}


def test_load_rejects_null_json(tmp_path: Path):
    p = tmp_path / "export_state.json"
    p.write_text("null", encoding="utf-8")
    assert load_export_state_from_disk(str(p)) == {}


def test_load_sanitizes_non_dict_sessions(tmp_path: Path):
    p = tmp_path / "export_state.json"
    p.write_text(
        json.dumps(
            {
                "lastExportTime": "2026-01-01T00:00:00",
                "exportedCount": 1,
                "sessions": [],
            }
        ),
        encoding="utf-8",
    )
    out = load_export_state_from_disk(str(p))
    assert out["sessions"] == {}
    assert out["lastExportTime"] == "2026-01-01T00:00:00"
    assert out["exportedCount"] == 1


def test_load_adds_sessions_when_missing_but_has_last_export(tmp_path: Path):
    p = tmp_path / "export_state.json"
    p.write_text(
        json.dumps({"lastExportTime": "2026-01-01T00:00:00", "exportedCount": 0}),
        encoding="utf-8",
    )
    out = load_export_state_from_disk(str(p))
    assert out["sessions"] == {}
    assert out["lastExportTime"] == "2026-01-01T00:00:00"


def test_load_legacy_flat_dict_unchanged_shape(tmp_path: Path):
    p = tmp_path / "export_state.json"
    legacy = {"uuid-one": 1740000000.0}
    p.write_text(json.dumps(legacy), encoding="utf-8")
    out = load_export_state_from_disk(str(p))
    assert out == {"sessions": legacy}


def test_export_state_lock_windows_branch_uses_msvcrt_when_no_fcntl(
    monkeypatch, tmp_path: Path
):
    """When ``fcntl`` is absent, use ``msvcrt.locking`` (cross-process on Windows)."""
    import utils.export_state_store as mod

    monkeypatch.setattr(mod, "fcntl", None)
    calls: list[tuple[int, int]] = []

    class FakeMsvcrt:
        LK_LOCK = 1
        LK_UNLCK = 2

        @staticmethod
        def locking(fd, mode, nbytes):
            calls.append((mode, nbytes))

    monkeypatch.setattr(mod, "msvcrt", FakeMsvcrt)

    state_file = tmp_path / "export_state.json"
    state_file.write_text("{}", encoding="utf-8")
    with mod.export_state_lock(str(state_file)):
        assert (FakeMsvcrt.LK_LOCK, 1) in calls
    assert calls[-1] == (FakeMsvcrt.LK_UNLCK, 1)


@pytest.mark.skipif(sys.platform != "win32", reason="requires Windows msvcrt")
def test_export_state_lock_real_msvcrt_roundtrip(tmp_path: Path) -> None:
    """Exercise real ``msvcrt.locking`` on a Windows runner (not FakeMsvcrt)."""
    state_file = tmp_path / "export_state.json"
    state_file.write_text("{}", encoding="utf-8")
    payload = {
        "sessions": {},
        "lastExportTime": "2026-01-01T00:00:00",
        "exportedCount": 0,
    }

    with export_state_lock(str(state_file)):
        atomic_write_export_state(payload, str(state_file))

    loaded = load_export_state_from_disk(str(state_file))
    assert loaded.get("exportedCount") == 0
    assert loaded.get("sessions") == {}
