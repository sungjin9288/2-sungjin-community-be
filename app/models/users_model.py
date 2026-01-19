import secrets
from app.common.security import hash_password

_users: dict[int, dict] = {}
_email_index: dict[str, int] = {}
_nickname_index: dict[str, int] = {}
_user_seq: int = 1

_sessions: dict[str, int] = {}

def get_user_by_id(user_id: int) -> dict | None:
    return _users.get(user_id)

def find_user_by_email(email: str) -> dict | None:
    uid = _email_index.get(email)
    return _users.get(uid) if uid else None

def is_email_exists(email: str) -> bool:
    return email in _email_index

def is_nickname_exists(nickname: str) -> bool:
    return nickname in _nickname_index

def create_user(email: str, password: str, nickname: str, profile_image_url: str = None) -> dict:
    global _user_seq
    user = {
        "id": _user_seq,
        "email": email,
        "password_hash": hash_password(password),
        "nickname": nickname,
        "profile_image_url": profile_image_url,
    }
    _users[_user_seq] = user
    _email_index[email] = _user_seq
    _nickname_index[nickname] = _user_seq
    _user_seq += 1
    return user

def update_user(user_id: int, nickname: str = None, profile_image_url: str = None, password_hash: str = None) -> dict:
    user = _users.get(user_id)
    if user:
        if nickname:
            old_nick = user["nickname"]
            if old_nick in _nickname_index:
                del _nickname_index[old_nick]
            user["nickname"] = nickname
            _nickname_index[nickname] = user_id
        
        if profile_image_url is not None:
            user["profile_image_url"] = profile_image_url
            
        if password_hash:
            user["password_hash"] = password_hash
    return user

def delete_user(user_id: int):
    user = _users.pop(user_id, None)
    if user:
        _email_index.pop(user["email"], None)
        _nickname_index.pop(user["nickname"], None)

def create_session(user_id: int) -> str:
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = user_id
    return session_id

def delete_session(session_id: str) -> None:
    _sessions.pop(session_id, None)

def get_user_id_by_session(session_id: str) -> int | None:
    return _sessions.get(session_id)