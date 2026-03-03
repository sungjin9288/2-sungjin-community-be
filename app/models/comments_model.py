from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.db_models import Comment
from app.models.base import to_dict as _to_dict


def list_comments(post_id: int, user_id: int | None = None) -> list[dict]:
    db = SessionLocal()
    try:
        comments = (
            db.query(Comment)
            .filter(Comment.post_id == post_id, Comment.deleted_at.is_(None))
            .all()
        )
        results = []
        for c in comments:
            c_dict = _to_dict(c)
            c_dict["author_nickname"] = c.owner.nickname if c.owner else "Unknown"
            c_dict["author_profile_image"] = c.owner.profile_image_url if c.owner else None
            c_dict["is_author"] = bool(user_id and c.user_id == user_id)
            results.append(c_dict)
        return results
    finally:
        db.close()


def find_comment(comment_id: int) -> dict | None:
    db = SessionLocal()
    try:
        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        return _to_dict(comment)
    finally:
        db.close()


def create_comment(user_id: int, post_id: int, content: str) -> dict:
    db = SessionLocal()
    try:
        new_comment = Comment(user_id=user_id, post_id=post_id, content=content)
        db.add(new_comment)
        db.commit()
        db.refresh(new_comment)

        res = _to_dict(new_comment)
        res["author_nickname"] = new_comment.owner.nickname
        res["author_profile_image"] = new_comment.owner.profile_image_url
        return res
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_comment(comment_id: int, content: str) -> dict | None:
    db = SessionLocal()
    try:
        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        if not comment:
            return None

        comment.content = content
        db.commit()
        db.refresh(comment)

        res = _to_dict(comment)
        res["author_nickname"] = comment.owner.nickname
        res["author_profile_image"] = comment.owner.profile_image_url
        return res
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_comment(comment_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(Comment).filter(Comment.id == comment_id).delete()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()