"""Exception types treated as session load/parse failures."""

import json

SESSION_LOAD_ERRORS: tuple[type[BaseException], ...] = (
    json.JSONDecodeError,
    KeyError,
    ValueError,
    OSError,
    FileNotFoundError,
)
