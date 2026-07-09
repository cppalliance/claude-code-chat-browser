"""Positive fixture: discriminant narrowing allows role-specific fields."""

from models.session import AssistantMessageDict, MessageDict, UserMessageDict

messages: list[MessageDict] = [
    {"role": "user", "text": "hello"},
    {"role": "assistant", "text": "hi", "thinking": "hmm"},
]
for msg in messages:
    if msg["role"] == "user":
        narrowed: UserMessageDict = msg
        _ = narrowed["slug"]
    elif msg["role"] == "assistant":
        narrowed_asst: AssistantMessageDict = msg
        _ = narrowed_asst["thinking"]
