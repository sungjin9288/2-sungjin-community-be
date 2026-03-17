from app.database import SessionLocal
from app.db_models import Comment
from app.models.base import to_dict as _to_dict
from app.models.social_model import get_hidden_user_ids


def _serialize_comment(comment: Comment, user_id: int | None = None) -> dict:
    payload = _to_dict(comment)
    payload["author_nickname"] = comment.owner.nickname if comment.owner else "Unknown"
    payload["author_profile_image"] = comment.owner.profile_image_url if comment.owner else None
    payload["is_author"] = bool(user_id and comment.user_id == user_id)
    payload["replies"] = []
    payload["reply_count"] = 0
    return payload


def list_comments(post_id: int, user_id: int | None = None) -> list[dict]:
    db = SessionLocal()
    try:
        query = (
            db.query(Comment)
            .filter(Comment.post_id == post_id, Comment.deleted_at.is_(None))
            .order_by(Comment.created_at.asc(), Comment.id.asc())
        )
        hidden_user_ids = get_hidden_user_ids(user_id)
        if hidden_user_ids:
            query = query.filter(Comment.user_id.notin_(hidden_user_ids))
        comments = query.all()

        serialized = {_comment.id: _serialize_comment(_comment, user_id) for _comment in comments}
        roots: list[dict] = []

        for comment in comments:
            current = serialized[comment.id]
            parent_id = comment.parent_comment_id
            if parent_id and parent_id in serialized:
                serialized[parent_id]["replies"].append(current)
                serialized[parent_id]["reply_count"] += 1
            else:
                roots.append(current)

        return roots
    finally:
        db.close()


def find_comment(comment_id: int) -> dict | None:
    db = SessionLocal()
    try:
        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        return _to_dict(comment)
    finally:
        db.close()


def create_comment(user_id: int, post_id: int, content: str, parent_comment_id: int | None = None) -> dict:
    db = SessionLocal()
    try:
        new_comment = Comment(
            user_id=user_id,
            post_id=post_id,
            content=content,
            parent_comment_id=parent_comment_id,
        )
        db.add(new_comment)
        db.commit()
        db.refresh(new_comment)

        res = _serialize_comment(new_comment, user_id)
        res["reply_count"] = 0
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
        return _serialize_comment(comment, comment.user_id)
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
