"""Positive fixture: discriminant narrowing allows role-specific fields."""

from models.session import MessageDict, UserMessageDict

messages: list[MessageDict] = [{"role": "user", "text": "hello"}]
for msg in messages:
    if msg["role"] == "user":
        narrowed: UserMessageDict = msg
        _ = narrowed.get("slug")
