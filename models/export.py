"""Export state file shapes."""

from typing import TypedDict


class ExportStateDict(TypedDict, total=False):
    lastExportTime: str
    exportedCount: int
    sessions: dict[str, float]
    exportDir: str
