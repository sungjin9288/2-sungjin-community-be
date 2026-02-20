from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.db_models import Session, User

SESSION_TTL_DAYS = 7


def _to_dict(obj):
    if not obj:
        return None
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
        user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
        return _to_dict(user)
    finally:
        db.close()


def get_user_by_id(user_id: int) -> dict | None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
        return _to_dict(user)
    finally:
        db.close()


def is_email_exists(email: str) -> bool:
    return find_user_by_email(email) is not None


def is_nickname_exists(nickname: str) -> bool:
    db = SessionLocal()
    try:
        exists = db.query(User.id).filter(User.nickname == nickname, User.deleted_at.is_(None)).first()
        return exists is not None
    finally:
        db.close()


def create_user(
    email: str,
    password_hash: str,
    nickname: str,
    profile_image_url: str | None = None,
) -> dict | None:
    db = SessionLocal()
    try:
        new_user = User(
            email=email,
            password=password_hash,
            nickname=nickname,
            profile_image_url=profile_image_url,
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


def update_user(user_id: int, **kwargs) -> dict | None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        if "nickname" in kwargs and kwargs["nickname"] is not None:
            user.nickname = kwargs["nickname"]
        if "profile_image_url" in kwargs:
            user.profile_image_url = kwargs["profile_image_url"]
        if "password_hash" in kwargs and kwargs["password_hash"]:
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


def create_session(user_id: int, ttl_days: int = SESSION_TTL_DAYS) -> str:
    db = SessionLocal()
    try:
        session_id = str(uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
        db.add(Session(session_id=session_id, user_id=user_id, expires_at=expires_at))
        db.commit()
        return session_id
    finally:
        db.close()


def get_user_id_by_session(session_id: str) -> int | None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        session = db.query(Session).filter(Session.session_id == session_id).first()
        if not session:
            return None

        # SQLite는 timezone-naive datetime을 저장하므로 비교 전 aware로 변환
        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now:
            db.delete(session)
            db.commit()
            return None

        return session.user_id
    finally:
        db.close()



def delete_session(session_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(Session).filter(Session.session_id == session_id).delete()
        db.commit()
    finally:
        db.close()
