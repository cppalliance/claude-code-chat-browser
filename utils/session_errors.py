"""Exception types treated as session load/parse failures."""

SESSION_LOAD_ERRORS: tuple[type[BaseException], ...] = (
    KeyError,
    ValueError,
    OSError,
)
