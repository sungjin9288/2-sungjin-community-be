from datetime import datetime, timedelta
import logging

from sqlalchemy import case, desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.db_models import Comment, Like, Post, PostTag, Tag

logger = logging.getLogger(__name__)


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


def _build_likes_map(db, post_ids: list[int]) -> dict[int, int]:
    if not post_ids:
        return {}
    rows = (
        db.query(Like.post_id, func.count(Like.id))
        .filter(Like.post_id.in_(post_ids))
        .group_by(Like.post_id)
        .all()
    )
    return {post_id: count for post_id, count in rows}


def _build_comments_map(db, post_ids: list[int]) -> dict[int, int]:
    if not post_ids:
        return {}
    rows = (
        db.query(Comment.post_id, func.count(Comment.id))
        .filter(Comment.post_id.in_(post_ids))
        .group_by(Comment.post_id)
        .all()
    )
    return {post_id: count for post_id, count in rows}


def _build_tags_map(db, post_ids: list[int]) -> dict[int, list[str]]:
    if not post_ids:
        return {}
    rows = (
        db.query(PostTag.post_id, Tag.name)
        .join(Tag, Tag.id == PostTag.tag_id)
        .filter(PostTag.post_id.in_(post_ids))
        .order_by(Tag.name.asc())
        .all()
    )
    tags_map: dict[int, list[str]] = {}
    for post_id, tag_name in rows:
        tags_map.setdefault(post_id, []).append(tag_name)
    return tags_map


def _build_liked_set(db, post_ids: list[int], current_user_id: int | None) -> set[int]:
    if not post_ids or not current_user_id:
        return set()
    rows = (
        db.query(Like.post_id)
        .filter(Like.user_id == current_user_id, Like.post_id.in_(post_ids))
        .all()
    )
    return {post_id for (post_id,) in rows}


def _serialize_post(
    post: Post,
    likes_count: int,
    comments_count: int,
    tags: list[str],
    current_user_id: int | None,
    liked_post_ids: set[int],
) -> dict:
    data = _to_dict(post)
    data["author_nickname"] = post.owner.nickname if post.owner else "Unknown"
    data["author_profile_image"] = post.owner.profile_image_url if post.owner else None
    data["likes_count"] = likes_count
    data["comments_count"] = comments_count
    data["views"] = post.view_count
    data["view_count"] = post.view_count
    data["tags"] = tags
    data["is_author"] = bool(current_user_id and post.user_id == current_user_id)
    data["is_liked"] = post.id in liked_post_ids
    return data


def _serialize_posts_batch(db, posts: list[Post], current_user_id: int | None) -> list[dict]:
    post_ids = [p.id for p in posts]
    likes_map = _build_likes_map(db, post_ids)
    comments_map = _build_comments_map(db, post_ids)
    tags_map = _build_tags_map(db, post_ids)
    liked_set = _build_liked_set(db, post_ids, current_user_id)

    return [
        _serialize_post(
            post=p,
            likes_count=likes_map.get(p.id, 0),
            comments_count=comments_map.get(p.id, 0),
            tags=tags_map.get(p.id, []),
            current_user_id=current_user_id,
            liked_post_ids=liked_set,
        )
        for p in posts
    ]


def list_posts(
    page: int = 1,
    limit: int = 10,
    current_user_id: int | None = None,
    sort: str = "latest",
    tag: str | None = None,
) -> list[dict]:
    db = SessionLocal()
    try:
        offset = (page - 1) * limit

        likes_subq = (
            db.query(Like.post_id.label("post_id"), func.count(Like.id).label("likes_count"))
            .group_by(Like.post_id)
            .subquery()
        )
        comments_subq = (
            db.query(Comment.post_id.label("post_id"), func.count(Comment.id).label("comments_count"))
            .group_by(Comment.post_id)
            .subquery()
        )

        query = db.query(Post).options(joinedload(Post.owner))
        if tag:
            query = (
                query.join(PostTag, PostTag.post_id == Post.id)
                .join(Tag, Tag.id == PostTag.tag_id)
                .filter(Tag.name == tag)
            )

        if sort == "hot":
            capped_views = case((Post.view_count > 200, 200), else_=Post.view_count)
            hot_score = (
                (func.coalesce(likes_subq.c.likes_count, 0) * 3.0)
                + (func.coalesce(comments_subq.c.comments_count, 0) * 2.0)
                + (capped_views * 0.1)
            )
            query = (
                query.outerjoin(likes_subq, likes_subq.c.post_id == Post.id)
                .outerjoin(comments_subq, comments_subq.c.post_id == Post.id)
                .order_by(desc(hot_score), desc(Post.created_at))
            )
        elif sort == "discussed":
            query = (
                query.outerjoin(comments_subq, comments_subq.c.post_id == Post.id)
                .order_by(desc(func.coalesce(comments_subq.c.comments_count, 0)), desc(Post.created_at))
            )
        else:
            query = query.order_by(desc(Post.created_at))

        posts = query.offset(offset).limit(limit).all()
        return _serialize_posts_batch(db, posts, current_user_id)
    except Exception as e:
        logger.error("failed to list posts: %s", e)
        raise
    finally:
        db.close()


def _get_or_create_tag(db, tag_name: str) -> Tag:
    tag = db.query(Tag).filter(Tag.name == tag_name).first()
    if tag:
        return tag
    tag = Tag(name=tag_name)
    db.add(tag)
    db.flush()
    return tag


def _replace_post_tags(db, post: Post, tags: list[str]) -> None:
    if post.post_tags:
        for post_tag in list(post.post_tags):
            db.delete(post_tag)
        db.flush()

    for tag_name in tags:
        tag = _get_or_create_tag(db, tag_name)
        db.add(PostTag(post_id=post.id, tag_id=tag.id))


def create_post(
    user_id: int,
    title: str,
    content: str,
    image_url: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    db = SessionLocal()
    try:
        new_post = Post(user_id=user_id, title=title, content=content, image_url=image_url)
        db.add(new_post)
        db.flush()

        if tags:
            _replace_post_tags(db, new_post, tags)

        db.commit()
        db.refresh(new_post)
        return _serialize_posts_batch(db, [new_post], current_user_id=user_id)[0]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def find_post(post_id: int, current_user_id: int | None = None) -> dict | None:
    db = SessionLocal()
    try:
        post = db.query(Post).options(joinedload(Post.owner)).filter(Post.id == post_id).first()
        if not post:
            return None
        return _serialize_posts_batch(db, [post], current_user_id)[0]
    finally:
        db.close()


def update_post(
    post_id: int,
    title: str,
    content: str,
    image_url: str | None = None,
    tags: list[str] | None = None,
) -> dict | None:
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return None

        post.title = title
        post.content = content
        if image_url is not None:
            post.image_url = image_url
        if tags is not None:
            _replace_post_tags(db, post, tags)

        db.commit()
        db.refresh(post)

        hydrated = db.query(Post).options(joinedload(Post.owner)).filter(Post.id == post_id).first()
        return _serialize_posts_batch(db, [hydrated], current_user_id=None)[0]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_post(post_id: int) -> None:
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            db.delete(post)
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def increment_views(post_id: int) -> None:
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            post.view_count += 1
            db.commit()
    finally:
        db.close()


def get_like_count(post_id: int) -> int:
    db = SessionLocal()
    try:
        return db.query(Like).filter(Like.post_id == post_id).count()
    finally:
        db.close()


def is_liked(user_id: int, post_id: int) -> bool:
    db = SessionLocal()
    try:
        like = db.query(Like).filter(Like.user_id == user_id, Like.post_id == post_id).first()
        return like is not None
    finally:
        db.close()


def add_like(user_id: int, post_id: int) -> bool:
    db = SessionLocal()
    try:
        db.add(Like(user_id=user_id, post_id=post_id))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def remove_like(user_id: int, post_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(Like).filter(Like.user_id == user_id, Like.post_id == post_id).delete()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_trending(
    days: int = 7,
    limit: int = 5,
    current_user_id: int | None = None,
) -> dict:
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        likes_subq = (
            db.query(Like.post_id.label("post_id"), func.count(Like.id).label("likes_count"))
            .group_by(Like.post_id)
            .subquery()
        )
        comments_subq = (
            db.query(Comment.post_id.label("post_id"), func.count(Comment.id).label("comments_count"))
            .group_by(Comment.post_id)
            .subquery()
        )

        capped_views = case((Post.view_count > 200, 200), else_=Post.view_count)
        hot_score = (
            (func.coalesce(likes_subq.c.likes_count, 0) * 3.0)
            + (func.coalesce(comments_subq.c.comments_count, 0) * 2.0)
            + (capped_views * 0.1)
        )

        top_posts = (
            db.query(Post)
            .options(joinedload(Post.owner))
            .outerjoin(likes_subq, likes_subq.c.post_id == Post.id)
            .outerjoin(comments_subq, comments_subq.c.post_id == Post.id)
            .filter(Post.created_at >= cutoff)
            .order_by(desc(hot_score), desc(Post.created_at))
            .limit(limit)
            .all()
        )

        top_tags_rows = (
            db.query(Tag.name, func.count(PostTag.id).label("count"))
            .join(PostTag, Tag.id == PostTag.tag_id)
            .join(Post, Post.id == PostTag.post_id)
            .filter(Post.created_at >= cutoff)
            .group_by(Tag.name)
            .order_by(desc(func.count(PostTag.id)), Tag.name.asc())
            .limit(limit)
            .all()
        )

        posts_payload = _serialize_posts_batch(db, top_posts, current_user_id)
        post_ids = [p["id"] for p in posts_payload]
        score_map = {}
        if post_ids:
            score_rows = (
                db.query(Post.id, hot_score)
                .outerjoin(likes_subq, likes_subq.c.post_id == Post.id)
                .outerjoin(comments_subq, comments_subq.c.post_id == Post.id)
                .filter(Post.id.in_(post_ids))
                .all()
            )
            score_map = {post_id: float(score) for post_id, score in score_rows}

        for item in posts_payload:
            item["trending_score"] = round(score_map.get(item["id"], 0.0), 2)

        return {
            "period_days": days,
            "top_tags": [{"name": name, "count": count} for name, count in top_tags_rows],
            "posts": posts_payload,
        }
    finally:
        db.close()
