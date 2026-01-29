from datetime import datetime
from app.database import SessionLocal
from app.db_models import User
from sqlalchemy.exc import IntegrityError

# ★ 수정: 날짜(datetime)를 문자열로 변환하는 로직 추가
def _to_dict(obj):
    if not obj: return None
    data = {}
    for c in obj.__table__.columns:
        val = getattr(obj, c.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        data[c.name] = val
    return data

def find_user_by_email(email: str) -> dict | None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        return _to_dict(user)
    finally:
        db.close()

def get_user_by_id(user_id: int) -> dict | None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        return _to_dict(user)
    finally:
        db.close()

def is_email_exists(email: str) -> bool:
    return find_user_by_email(email) is not None

def is_nickname_exists(nickname: str) -> bool:
    db = SessionLocal()
    try:
        exists = db.query(User.id).filter(User.nickname == nickname).first()
        return exists is not None
    finally:
        db.close()

def create_user(email, password_hash, nickname, profile_image_url=None):
    db = SessionLocal()
    try:
        new_user = User(
            email=email,
            password=password_hash,
            nickname=nickname,
            profile_image_url=profile_image_url
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return _to_dict(new_user)
    except IntegrityError:
        db.rollback()
        return None
    finally:
        db.close()

def update_user(user_id, **kwargs) -> dict | None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        if "nickname" in kwargs and kwargs["nickname"]:
            user.nickname = kwargs["nickname"]
        if "profile_image_url" in kwargs:
            user.profile_image_url = kwargs["profile_image_url"]
        if "password_hash" in kwargs:
            user.password = kwargs["password_hash"]

        db.commit()
        db.refresh(user)
        return _to_dict(user)
    finally:
        db.close()

def delete_user(user_id: int) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            db.delete(user)
            db.commit()
    finally:
        db.close()

# 세션 관리 (메모리 방식 유지)
_sessions = {}
def create_session(user_id: int) -> str:
    import uuid
    session_id = str(uuid.uuid4())
    _sessions[session_id] = user_id
    return session_id

def get_user_id_by_session(session_id: str) -> int | None:
    return _sessions.get(session_id)

def delete_session(session_id: str):
    _sessions.pop(session_id, None)