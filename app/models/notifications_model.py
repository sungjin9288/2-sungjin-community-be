from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.db_models import Notification, User
from app.models.base import to_dict as _to_dict


def _serialize_user(user: User | None) -> dict | None:
    if not user:
        return None
    return {
        "id": user.id,
        "email": user.email,
        "nickname": user.nickname,
        "profile_image_url": user.profile_image_url,
    }


def _serialize_notification(notification: Notification) -> dict:
    data = _to_dict(notification)
    data["actor"] = _serialize_user(notification.actor)
    return data


def create_notification(
    user_id: int,
    *,
    actor_id: int | None,
    notification_type: str,
    title: str,
    body: str | None = None,
    link_url: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> dict:
    db = SessionLocal()
    try:
        notification = Notification(
            user_id=user_id,
            actor_id=actor_id,
            type=notification_type,
            title=title,
            body=body,
            link_url=link_url,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        _ = notification.actor
        return _serialize_notification(notification)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_notifications(user_id: int, unread_only: bool = False, limit: int = 50) -> list[dict]:
    db = SessionLocal()
    try:
        query = (
            db.query(Notification)
            .options(joinedload(Notification.actor))
            .filter(Notification.user_id == user_id, Notification.deleted_at.is_(None))
        )
        if unread_only:
            query = query.filter(Notification.is_read.is_(False))
        notifications = query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit).all()
        return [_serialize_notification(item) for item in notifications]
    finally:
        db.close()


def count_unread_notifications(user_id: int) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.deleted_at.is_(None),
                Notification.is_read.is_(False),
            )
            .count()
        )
    finally:
        db.close()


def mark_notification_read(user_id: int, notification_id: int) -> dict | None:
    db = SessionLocal()
    try:
        notification = (
            db.query(Notification)
            .options(joinedload(Notification.actor))
            .filter(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.deleted_at.is_(None),
            )
            .first()
        )
        if not notification:
            return None
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
        return _serialize_notification(notification)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def mark_all_notifications_read(user_id: int) -> int:
    db = SessionLocal()
    try:
        notifications = (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.deleted_at.is_(None),
                Notification.is_read.is_(False),
            )
            .all()
        )
        now = datetime.now(timezone.utc)
        for notification in notifications:
            notification.is_read = True
            notification.read_at = now
        db.commit()
        return len(notifications)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
