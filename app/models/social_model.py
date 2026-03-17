from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.db_models import Comment, DirectMessage, Post, Report, User, UserBlock
from app.models.base import to_dict as _to_dict

ALLOWED_REPORT_TARGETS = {"post", "comment", "user", "message"}


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "nickname": user.nickname,
        "profile_image_url": user.profile_image_url,
    }


def get_hidden_user_ids(user_id: int | None) -> set[int]:
    if not user_id:
        return set()

    db = SessionLocal()
    try:
        blocked = {
            blocked_user_id
            for (blocked_user_id,) in db.query(UserBlock.blocked_user_id)
            .filter(UserBlock.blocker_id == user_id)
            .all()
        }
        blocked_by = {
            blocker_id
            for (blocker_id,) in db.query(UserBlock.blocker_id)
            .filter(UserBlock.blocked_user_id == user_id)
            .all()
        }
        return blocked | blocked_by
    finally:
        db.close()


def is_blocked_between(left_user_id: int, right_user_id: int) -> bool:
    db = SessionLocal()
    try:
        relation = (
            db.query(UserBlock)
            .filter(
                or_(
                    and_(UserBlock.blocker_id == left_user_id, UserBlock.blocked_user_id == right_user_id),
                    and_(UserBlock.blocker_id == right_user_id, UserBlock.blocked_user_id == left_user_id),
                )
            )
            .first()
        )
        return relation is not None
    finally:
        db.close()


def list_blocked_users(blocker_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(UserBlock)
            .options(joinedload(UserBlock.blocked_user))
            .filter(UserBlock.blocker_id == blocker_id)
            .order_by(UserBlock.created_at.desc(), UserBlock.id.desc())
            .all()
        )
        return [
            {
                "id": row.id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "user": _serialize_user(row.blocked_user),
            }
            for row in rows
            if row.blocked_user and row.blocked_user.deleted_at is None
        ]
    finally:
        db.close()


def create_block(blocker_id: int, blocked_user_id: int) -> dict | None:
    db = SessionLocal()
    try:
        relation = UserBlock(blocker_id=blocker_id, blocked_user_id=blocked_user_id)
        db.add(relation)
        db.commit()
        db.refresh(relation)
        _ = relation.blocked_user
        return {
            "id": relation.id,
            "created_at": relation.created_at.isoformat() if relation.created_at else None,
            "user": _serialize_user(relation.blocked_user),
        }
    except IntegrityError:
        db.rollback()
        return None
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_block(blocker_id: int, blocked_user_id: int) -> bool:
    db = SessionLocal()
    try:
        deleted = (
            db.query(UserBlock)
            .filter(UserBlock.blocker_id == blocker_id, UserBlock.blocked_user_id == blocked_user_id)
            .delete()
        )
        db.commit()
        return bool(deleted)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_report(
    reporter_id: int,
    *,
    target_type: str,
    target_id: int,
    reason: str,
    description: str | None = None,
) -> dict:
    db = SessionLocal()
    try:
        normalized_type = (target_type or "").strip().lower()
        if normalized_type not in ALLOWED_REPORT_TARGETS:
            raise ValueError("unsupported_target_type")

        target = None
        reported_user_id = None
        if normalized_type == "post":
            target = db.query(Post).filter(Post.id == target_id, Post.deleted_at.is_(None)).first()
            reported_user_id = target.user_id if target else None
        elif normalized_type == "comment":
            target = db.query(Comment).filter(Comment.id == target_id, Comment.deleted_at.is_(None)).first()
            reported_user_id = target.user_id if target else None
        elif normalized_type == "user":
            target = db.query(User).filter(User.id == target_id, User.deleted_at.is_(None)).first()
            reported_user_id = target.id if target else None
        elif normalized_type == "message":
            target = db.query(DirectMessage).filter(DirectMessage.id == target_id, DirectMessage.deleted_at.is_(None)).first()
            reported_user_id = target.sender_id if target else None

        if not target:
            return None

        report = Report(
            reporter_id=reporter_id,
            reported_user_id=reported_user_id,
            target_type=normalized_type,
            target_id=target_id,
            reason=reason,
            description=description,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        payload = _to_dict(report)
        payload["reporter"] = _serialize_user(report.reporter)
        payload["reported_user"] = _serialize_user(report.reported_user) if report.reported_user else None
        return payload
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
