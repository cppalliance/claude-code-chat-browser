"""Negative fixture: role-inappropriate MessageDict access must fail mypy strict."""

from models.session import MessageDict, UserMessageDict

user_msg: UserMessageDict = {"role": "user", "text": "hello"}
_ = user_msg["thinking"]

union_msg: MessageDict = {"role": "user", "text": "hello"}
_ = union_msg["thinking"]
