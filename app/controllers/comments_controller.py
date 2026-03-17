from fastapi.responses import JSONResponse

from app.common.exceptions import (
    BusinessException,
    ErrorCode,
    ForbiddenError,
    InvalidRequestFormatError,
    MissingRequiredFieldsError,
    PostNotFoundError,
    CommentNotFoundError,
)
from app.common.responses import created, ok
from app.models import comments_model, notifications_model, posts_model, social_model


def _validate_comment(content: str) -> None:
    if len(content) > 500:
        raise BusinessException(
            ErrorCode.INVALID_REQUEST_FORMAT,
            "댓글은 최대 500자까지 가능합니다.",
        )


def list_comments(post_id: int, user_id: int | None = None) -> JSONResponse:
    if not posts_model.find_post(post_id, user_id):
        raise PostNotFoundError()

    comments = comments_model.list_comments(post_id, user_id)
    return ok(message="read_comments_success", data=comments)


def create_comment(user_id: int, post_id: int, payload: dict) -> JSONResponse:
    content = (payload.get("content") or "").strip()
    parent_comment_id = payload.get("parent_comment_id")

    if not content:
        raise MissingRequiredFieldsError("댓글 내용을 입력해주세요.")

    _validate_comment(content)

    post = posts_model.find_post(post_id, user_id)
    if not post:
        raise PostNotFoundError()

    parent_comment = None
    if parent_comment_id is not None:
        parent_comment = comments_model.find_comment(parent_comment_id)
        if not parent_comment or parent_comment["post_id"] != post_id:
            raise CommentNotFoundError("답글 대상 댓글을 찾을 수 없습니다.")
        if social_model.is_blocked_between(user_id, parent_comment["user_id"]):
            raise ForbiddenError("차단 관계의 사용자 댓글에는 답글을 작성할 수 없습니다.")

    comment = comments_model.create_comment(user_id, post_id, content, parent_comment_id=parent_comment_id)

    if post.get("user_id") and post["user_id"] != user_id:
        notifications_model.create_notification(
            post["user_id"],
            actor_id=user_id,
            notification_type="comment",
            title="내 게시글에 새로운 댓글이 달렸습니다.",
            body=post.get("title"),
            link_url=f"/posts/{post_id}",
            entity_type="post",
            entity_id=post_id,
        )

    if parent_comment and parent_comment.get("user_id") not in {None, user_id, post.get("user_id")}:
        notifications_model.create_notification(
            parent_comment["user_id"],
            actor_id=user_id,
            notification_type="comment_reply",
            title="내 댓글에 새로운 답글이 달렸습니다.",
            body=content[:100],
            link_url=f"/posts/{post_id}",
            entity_type="comment",
            entity_id=parent_comment_id,
        )

    return created(message="comment_created", data=comment)


def update_comment(user_id: int, post_id: int, comment_id: int, payload: dict) -> JSONResponse:
    comment = comments_model.find_comment(comment_id)
    if not comment:
        raise CommentNotFoundError()

    if comment["post_id"] != post_id:
        raise CommentNotFoundError()

    if comment["user_id"] != user_id:
        raise ForbiddenError("댓글 수정 권한이 없습니다.")

    content = (payload.get("content") or "").strip()
    if not content:
        raise MissingRequiredFieldsError("댓글 내용을 입력해주세요.")

    _validate_comment(content)

    updated = comments_model.update_comment(comment_id, content)
    if not updated:
        raise CommentNotFoundError()

    return ok(message="comment_updated", data=updated)


def delete_comment(user_id: int, post_id: int, comment_id: int) -> JSONResponse:
    comment = comments_model.find_comment(comment_id)
    if not comment:
        raise CommentNotFoundError()

    if comment["post_id"] != post_id:
        raise CommentNotFoundError()

    if comment["user_id"] != user_id:
        raise ForbiddenError("댓글 삭제 권한이 없습니다.")

    comments_model.delete_comment(comment_id)
    return ok(message="comment_deleted", data=None)
