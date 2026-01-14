from __future__ import annotations

import uuid
from typing import Dict, Optional

_users: Dict[int, dict] = {}
_email_index: Dict[str, int] = {}
_nickname_index: Dict[str, int] = {}
_sessions: Dict[str, int] = {}

_user_seq: int = 1


def seed() -> None:

    if is_email_exists("start@community.com"):
        return
    create_user(email="start@community.com", password="start21", nickname="starter")


def create_user(email: str, password: str, nickname: str) -> dict:
    global _user_seq

    user = {
        "id": _user_seq,
        "email": email,
        "password": password,
        "nickname": nickname,
    }

    _users[_user_seq] = user
    _email_index[email] = _user_seq
    _nickname_index[nickname] = _user_seq

    _user_seq += 1
    return user


def find_user_by_email(email: str) -> Optional[dict]:
    user_id = _email_index.get(email)
    if user_id is None:
        return None
    return _users.get(user_id)


def find_user_by_id(user_id: int) -> Optional[dict]:
    return _users.get(user_id)


def is_email_exists(email: str) -> bool:
    return email in _email_index


def is_nickname_exists(nickname: str) -> bool:
    return nickname in _nickname_index


def create_session(user_id: int) -> str:
    token = str(uuid.uuid4())
    _sessions[token] = user_id
    return token


def get_user_id_by_token(token: str) -> Optional[int]:
    return _sessions.get(token)


def delete_session(token: str) -> None:
    _sessions.pop(token, None)
