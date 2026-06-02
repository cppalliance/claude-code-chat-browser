"""Flask app that serves the web GUI for browsing sessions."""

__version__ = "0.1.0"

import argparse
import os
import sys

from flask import Flask

from api.projects import projects_bp
from api.sessions import sessions_bp
from api.search import search_bp
from api.export_api import export_bp
from utils.exclusion_rules import resolve_exclusion_rules_path, load_rules


def is_loopback_host(host: str) -> bool:
    """True if ``host`` binds only to the local machine (safe with ``--debug``)."""
    h = (host or "").strip().lower()
    if h in ("127.0.0.1", "localhost", "::1"):
        return True
    if h.startswith("127.") and h.count(".") == 3:
        parts = h.split(".")
        try:
            return len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False
    return False


def validate_startup_cli(args: argparse.Namespace) -> None:
    """Refuse ``--debug`` when ``--host`` is reachable off loopback."""
    if args.debug and not is_loopback_host(args.host):
        print(
            "error: --debug is only allowed with a loopback --host "
            "(127.0.0.1, localhost, ::1, or 127.x.x.x). "
            "Combining --debug with a network-visible --host exposes the "
            "Werkzeug debugger and session data to other machines.",
            file=sys.stderr,
        )
        raise SystemExit(1)


def create_app(
    base_dir: str | None = None,
    exclusion_rules_path: str | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["CLAUDE_PROJECTS_DIR"] = base_dir

    resolved = resolve_exclusion_rules_path(exclusion_rules_path)
    app.config["EXCLUSION_RULES_PATH"] = resolved
    app.config["EXCLUSION_RULES"] = load_rules(resolved)

    app.register_blueprint(projects_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(export_bp)

    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    return app


def build_cli_parser() -> argparse.ArgumentParser:
    """CLI argument parser for ``python app.py`` (stdlib only; safe to import in tests)."""
    parser = argparse.ArgumentParser(description="Claude Code Chat Browser")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable Flask/Werkzeug debug mode (never use with --host 0.0.0.0 on untrusted networks).",
    )
    parser.add_argument("--base-dir", default=None, help="Override Claude projects dir")
    parser.add_argument(
        "--exclude-rules", "-e",
        default=None,
        metavar="PATH",
        help="Path to exclusion rules file (sensitive sessions are omitted). "
             "If omitted, uses ~/.claude-code-chat-browser/exclusion-rules.txt if present.",
    )
    return parser


if __name__ == "__main__":
    args = build_cli_parser().parse_args()
    validate_startup_cli(args)

    app = create_app(base_dir=args.base_dir, exclusion_rules_path=args.exclude_rules)
    print(f"Claude Code Chat Browser running at http://{args.host}:{args.port}")
    # Reloader follows --debug on Unix only (Werkzeug file watcher, not the interactive debugger).
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=args.debug and (sys.platform != "win32"),
    )
