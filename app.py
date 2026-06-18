"""Flask app that serves the web GUI for browsing sessions."""

__version__ = "0.1.0"

import argparse
import sys

from flask import Flask

from api.export_api import export_bp
from api.projects import projects_bp
from api.search import search_bp
from api.sessions import sessions_bp
from utils.exclusion_rules import load_rules, resolve_exclusion_rules_path

# Content-Security-Policy for all Flask responses. 'unsafe-inline' in style-src is
# required because highlight.js themes apply inline styles; can be tightened with
# nonces later. script-src lists cdnjs only — keep in sync with SRI <script>/<link>
# sources in static/index.html.
CSP_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' https://cdnjs.cloudflare.com",
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com",
        "img-src 'self' data:",
        "connect-src 'self'",
        "font-src 'self'",
        "object-src 'none'",
        "form-action 'self'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
    ]
)


def _normalize_bind_host(host: str) -> str:
    """Lowercase host for checks; strip optional IPv6 brackets (e.g. ``[::1]`` → ``::1``)."""
    h = (host or "").strip().lower()
    if len(h) >= 2 and h.startswith("[") and h.endswith("]"):
        return h[1:-1]
    return h


def is_loopback_host(host: str) -> bool:
    """True if ``host`` binds only to the local machine (safe with ``--debug``).

    Accepts ``127.0.0.1``, ``localhost``, ``::1``, ``[::1]``, and other ``127.x.x.x`` addresses.
    Rejects all-interfaces forms such as ``0.0.0.0`` and bare ``::`` (not loopback).
    """
    h = _normalize_bind_host(host)
    if h in ("127.0.0.1", "localhost", "::1"):
        return True
    if h.startswith("127.") and h.count(".") == 3:
        parts = h.split(".")
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False
    return False


def format_listen_url(host: str, port: int) -> str:
    """Return a valid ``http://`` URL for the startup banner (IPv6 hosts bracketed)."""
    h = (host or "").strip()
    if not h:
        raise ValueError("host must not be empty")
    if h.startswith("[") and h.endswith("]"):
        display_host = h
    elif ":" in h:
        display_host = f"[{h}]"
    else:
        display_host = h
    return f"http://{display_host}:{port}"


def validate_startup_cli(args: argparse.Namespace) -> None:
    """Refuse ``--debug`` when ``--host`` is reachable off loopback."""
    if args.debug and not is_loopback_host(args.host):
        print(
            "error: --debug is only allowed with a loopback --host "
            "(127.0.0.1, localhost, ::1, [::1], or 127.x.x.x). "
            "Combining --debug with a network-visible --host exposes the "
            "Werkzeug debugger and session data to other machines.",
            file=sys.stderr,
        )
        sys.exit(1)


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

    @app.after_request
    def set_security_headers(response):
        # Always set — do not use setdefault; a blueprint must not weaken CSP.
        response.headers["Content-Security-Policy"] = CSP_POLICY
        return response

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
        help=(
            "Enable Flask/Werkzeug debug mode "
            "(never use with --host 0.0.0.0 on untrusted networks)."
        ),
    )
    parser.add_argument("--base-dir", default=None, help="Override Claude projects dir")
    parser.add_argument(
        "--exclude-rules",
        "-e",
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
    print(f"Claude Code Chat Browser running at {format_listen_url(args.host, args.port)}")
    # Reloader follows --debug on Unix only (Werkzeug file watcher, not the interactive debugger).
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=args.debug and (sys.platform != "win32"),
    )
