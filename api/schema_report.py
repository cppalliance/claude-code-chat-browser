"""Schema drift report endpoint."""

from flask import Blueprint

from api._flask_types import FlaskReturn, json_response
from utils.schema_drift import get_schema_report

schema_report_bp = Blueprint("schema_report", __name__)


@schema_report_bp.route("/api/schema-report")
def schema_report() -> FlaskReturn:
    """Return known/new/missing JSONL field paths from recent parse runs."""
    return json_response(get_schema_report())
