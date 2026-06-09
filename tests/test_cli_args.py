"""
Regression tests for CLI argument parity between claude-code-chat-browser and
cursor-chat-browser-python.

Every flag/default documented here must match the reference (cursor) project so
that users switching between the two tools experience zero CLI friction.

Run:
    pytest tests/test_cli_args.py -v
"""

import argparse
import ast
import os
import sys

import pytest

# Ensure the repo root is on sys.path when tests are run from any directory.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from app import build_cli_parser, format_listen_url, is_loopback_host, validate_startup_cli
from scripts.export import build_parser


def _is_app_run_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "run"
        and isinstance(func.value, ast.Name)
        and func.value.id == "app"
    )


def _call_passes_hardcoded_debug_true(call: ast.Call) -> bool:
    """True if this Call passes literal True for debug (kwarg or positional)."""
    for kw in call.keywords:
        if kw.arg == "debug" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    for arg in call.args:
        if isinstance(arg, ast.Constant) and arg.value is True:
            return True
    return False


def _debug_kwarg_uses_args(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg != "debug":
            continue
        val = kw.value
        return (
            isinstance(val, ast.Attribute)
            and isinstance(val.value, ast.Name)
            and val.value.id == "args"
            and val.attr == "debug"
        )
    return False


def _is_args_debug(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "args"
        and node.attr == "debug"
    )


def _is_sys_platform_ne_win32(node: ast.AST) -> bool:
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        return False
    if not isinstance(node.ops[0], ast.NotEq):
        return False
    left = node.left
    if not (
        isinstance(left, ast.Attribute)
        and isinstance(left.value, ast.Name)
        and left.value.id == "sys"
        and left.attr == "platform"
    ):
        return False
    right = node.comparators[0]
    if isinstance(right, ast.Constant):
        return right.value == "win32"
    return isinstance(right, ast.Str) and right.s == "win32"  # py<3.8


def _is_debug_and_platform_guard(node: ast.AST) -> bool:
    """True for ``args.debug and (sys.platform != "win32")`` in either operand order."""
    if (
        not isinstance(node, ast.BoolOp)
        or not isinstance(node.op, ast.And)
        or len(node.values) != 2
    ):
        return False
    a, b = node.values
    return (_is_args_debug(a) and _is_sys_platform_ne_win32(b)) or (
        _is_args_debug(b) and _is_sys_platform_ne_win32(a)
    )


def _use_reloader_kwarg_tied_to_debug(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg == "use_reloader":
            return _is_debug_and_platform_guard(kw.value)
    return False


# ---------------------------------------------------------------------------
# export.py argument tests
# ---------------------------------------------------------------------------

class TestExportParserFlags:
    """Every flag that cursor's export.py exposes must also exist here."""

    def setup_method(self):
        self.parser = build_parser()

    def _parse(self, argv: list[str]) -> argparse.Namespace:
        return self.parser.parse_args(argv)

    # -- --since ----------------------------------------------------------------

    def test_since_defaults_to_none_at_top_level(self):
        args = self._parse([])
        assert args.since is None  # default; cmd_export normalises to "all"

    def test_since_all(self):
        args = self._parse(["--since", "all"])
        assert args.since == "all"

    def test_since_last(self):
        args = self._parse(["--since", "last"])
        assert args.since == "last"

    def test_since_invalid_value_raises(self):
        with pytest.raises(SystemExit):
            self._parse(["--since", "yesterday"])

    def test_since_subcommand_default_is_all(self):
        args = self._parse(["export"])
        assert args.since == "all"

    def test_since_subcommand_last(self):
        args = self._parse(["export", "--since", "last"])
        assert args.since == "last"

    def test_since_incremental(self):
        args = self._parse(["--since", "incremental"])
        assert args.since == "incremental"

    def test_since_before_export_subcommand_recovered(self):
        """Flags before ``export`` must not be lost to subparser defaults."""
        from scripts import export as export_mod

        argv = ["--since", "last", "export"]
        args = self._parse(argv)
        assert args.since == "all"  # argparse quirk without recovery
        for k, v in export_mod._prefixed_export_option_overrides(argv).items():
            setattr(args, k, v)
        assert args.since == "last"

    def test_since_incremental_before_export_recovered(self):
        from scripts import export as export_mod

        argv = ["--since", "incremental", "export"]
        args = self._parse(argv)
        assert args.since == "all"
        for k, v in export_mod._prefixed_export_option_overrides(argv).items():
            setattr(args, k, v)
        assert args.since == "incremental"

    def test_prefixed_out_before_export(self):
        from scripts import export as export_mod

        argv = ["--out", "/tmp/z", "export"]
        args = self._parse(argv)
        assert args.out is None
        for k, v in export_mod._prefixed_export_option_overrides(argv).items():
            setattr(args, k, v)
        assert args.out == "/tmp/z"

    # -- --out ------------------------------------------------------------------

    def test_out_default_is_none(self):
        args = self._parse([])
        assert args.out is None  # cmd_export normalises to os.getcwd()

    def test_out_explicit(self):
        args = self._parse(["--out", "/tmp/exports"])
        assert args.out == "/tmp/exports"

    def test_out_subcommand(self):
        args = self._parse(["export", "--out", "/tmp/exports"])
        assert args.out == "/tmp/exports"

    # -- --no-zip ---------------------------------------------------------------

    def test_no_zip_default_false(self):
        args = self._parse([])
        assert args.no_zip is False

    def test_no_zip_flag(self):
        args = self._parse(["--no-zip"])
        assert args.no_zip is True

    def test_no_zip_subcommand(self):
        args = self._parse(["export", "--no-zip"])
        assert args.no_zip is True

    # -- --exclude-rules / -e  (cursor parity) ----------------------------------

    def test_exclude_rules_long_form_default_none(self):
        args = self._parse([])
        assert args.exclude_rules is None

    def test_exclude_rules_long_form(self):
        args = self._parse(["--exclude-rules", "/path/to/rules.txt"])
        assert args.exclude_rules == "/path/to/rules.txt"

    def test_exclude_rules_short_form(self):
        args = self._parse(["-e", "/path/to/rules.txt"])
        assert args.exclude_rules == "/path/to/rules.txt"

    def test_exclude_rules_subcommand_long(self):
        args = self._parse(["export", "--exclude-rules", "/path/rules.txt"])
        assert args.exclude_rules == "/path/rules.txt"

    def test_exclude_rules_subcommand_short(self):
        args = self._parse(["export", "-e", "/path/rules.txt"])
        assert args.exclude_rules == "/path/rules.txt"

    # -- --base-dir -------------------------------------------------------------

    def test_base_dir_default_none(self):
        args = self._parse([])
        assert args.base_dir is None

    def test_base_dir_explicit(self):
        args = self._parse(["--base-dir", "/home/user/.claude/projects"])
        assert args.base_dir == "/home/user/.claude/projects"

    def test_base_dir_subcommand(self):
        args = self._parse(["export", "--base-dir", "/home/user/.claude/projects"])
        assert args.base_dir == "/home/user/.claude/projects"

    # -- --format ---------------------------------------------------------------

    def test_format_default_none_at_top_level(self):
        args = self._parse([])
        assert args.format is None  # cmd_export normalises to "md"

    def test_format_md(self):
        args = self._parse(["--format", "md"])
        assert args.format == "md"

    def test_format_json(self):
        args = self._parse(["--format", "json"])
        assert args.format == "json"

    def test_format_both(self):
        args = self._parse(["--format", "both"])
        assert args.format == "both"

    def test_format_invalid_raises(self):
        with pytest.raises(SystemExit):
            self._parse(["--format", "csv"])

    # -- subcommand dispatch ----------------------------------------------------

    def test_no_subcommand_command_attr_is_none(self):
        args = self._parse([])
        assert getattr(args, "command", None) is None

    def test_list_subcommand(self):
        args = self._parse(["list"])
        assert args.command == "list"

    def test_stats_subcommand(self):
        args = self._parse(["stats"])
        assert args.command == "stats"

    def test_export_subcommand(self):
        args = self._parse(["export"])
        assert args.command == "export"

    # -- --help does not raise (just exits 0) -----------------------------------

    def test_help_exits_zero(self):
        with pytest.raises(SystemExit) as exc_info:
            self._parse(["--help"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# app.py argument tests
# ---------------------------------------------------------------------------

class TestAppArgparse:
    """app.py CLI must expose the same flags as cursor's app.py."""

    def test_host_default_is_localhost(self):
        """Default host must be 127.0.0.1 to match cursor which binds to localhost only."""
        parser = build_cli_parser()
        args = parser.parse_args([])
        assert args.host == "127.0.0.1"

    def test_host_override(self):
        parser = build_cli_parser()
        args = parser.parse_args(["--host", "127.0.0.1"])
        assert args.host == "127.0.0.1"

    def test_debug_default_is_false(self):
        parser = build_cli_parser()
        args = parser.parse_args([])
        assert args.debug is False

    def test_debug_explicit_true(self):
        parser = build_cli_parser()
        args = parser.parse_args(["--debug"])
        assert args.debug is True

    @pytest.mark.parametrize(
        "host", ["127.0.0.1", "localhost", "::1", "[::1]", "127.0.0.2"]
    )
    def test_is_loopback_host_accepts_loopback(self, host: str) -> None:
        assert is_loopback_host(host)

    @pytest.mark.parametrize(
        "host",
        [
            "0.0.0.0",
            "192.168.1.1",
            "",
            "example.com",
            "127.0.0.",
            "127.256.0.0",
            "127.-1.0.0",
        ],
    )
    def test_is_loopback_host_rejects_non_loopback(self, host: str) -> None:
        assert not is_loopback_host(host)

    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
    def test_validate_startup_cli_allows_loopback_debug(self, host: str) -> None:
        parser = build_cli_parser()
        args = parser.parse_args(["--host", host, "--debug"])
        validate_startup_cli(args)

    def test_validate_startup_cli_rejects_non_loopback_debug(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        parser = build_cli_parser()
        args = parser.parse_args(["--host", "0.0.0.0", "--debug"])
        with pytest.raises(SystemExit) as exc_info:
            validate_startup_cli(args)
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "debug" in err.lower()
        assert "loopback" in err.lower()

    @pytest.mark.parametrize(
        ("host", "port", "expected"),
        [
            ("127.0.0.1", 5000, "http://127.0.0.1:5000"),
            ("::1", 8080, "http://[::1]:8080"),
            ("[::1]", 8080, "http://[::1]:8080"),
        ],
    )
    def test_format_listen_url(self, host: str, port: int, expected: str) -> None:
        assert format_listen_url(host, port) == expected

    def test_format_listen_url_rejects_empty_host(self) -> None:
        with pytest.raises(ValueError, match="host must not be empty"):
            format_listen_url("", 5000)

    def test_validate_startup_cli_allows_non_loopback_without_debug(self) -> None:
        parser = build_cli_parser()
        args = parser.parse_args(["--host", "0.0.0.0"])
        validate_startup_cli(args)

    def test_app_py_debug_not_hardcoded_true(self):
        """app.run() must wire debug from args, not a literal True."""
        app_path = os.path.join(REPO_ROOT, "app.py")
        with open(app_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=app_path)
        app_run_calls = [n for n in ast.walk(tree) if _is_app_run_call(n)]
        assert app_run_calls, "expected at least one app.run() call in app.py"
        assert not any(_call_passes_hardcoded_debug_true(c) for c in app_run_calls)
        assert any(_debug_kwarg_uses_args(c) for c in app_run_calls)

    def test_port_default(self):
        parser = build_cli_parser()
        args = parser.parse_args([])
        assert args.port == 5000

    def test_port_override(self):
        parser = build_cli_parser()
        args = parser.parse_args(["--port", "8080"])
        assert args.port == 8080

    def test_base_dir_default_none(self):
        parser = build_cli_parser()
        args = parser.parse_args([])
        assert args.base_dir is None

    def test_base_dir_override(self):
        parser = build_cli_parser()
        args = parser.parse_args(["--base-dir", "/tmp/projects"])
        assert args.base_dir == "/tmp/projects"

    def test_exclude_rules_default_none(self):
        parser = build_cli_parser()
        args = parser.parse_args([])
        assert args.exclude_rules is None

    def test_exclude_rules_long_form(self):
        parser = build_cli_parser()
        args = parser.parse_args(["--exclude-rules", "/tmp/rules.txt"])
        assert args.exclude_rules == "/tmp/rules.txt"

    def test_exclude_rules_short_form(self):
        """Cursor's app.py uses -e as the short form; claude must too."""
        parser = build_cli_parser()
        args = parser.parse_args(["-e", "/tmp/rules.txt"])
        assert args.exclude_rules == "/tmp/rules.txt"

    def test_app_py_actual_argparse_has_exclude_rules(self):
        """Smoke-test: import app module and verify argparse accepts -e."""
        # Lightweight check: parse the app.py source for the flag definition
        app_path = os.path.join(REPO_ROOT, "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            src = f.read()
        assert '"--exclude-rules"' in src or "'--exclude-rules'" in src
        assert '"-e"' in src

    def test_app_py_host_default_is_localhost(self):
        """app.py source must declare 127.0.0.1 as the --host default, matching cursor."""
        app_path = os.path.join(REPO_ROOT, "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            src = f.read()
        assert '"127.0.0.1"' in src

    def test_app_py_use_reloader_is_platform_aware(self):
        """use_reloader must be ``args.debug and (sys.platform != \"win32\")``."""
        app_path = os.path.join(REPO_ROOT, "app.py")
        with open(app_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=app_path)
        app_run_calls = [n for n in ast.walk(tree) if _is_app_run_call(n)]
        assert app_run_calls
        assert all(_use_reloader_kwarg_tied_to_debug(c) for c in app_run_calls)
