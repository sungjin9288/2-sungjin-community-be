from fastapi.responses import JSONResponse

from app.common.responses import ok, created, bad_request, unauthorized, not_found, server_error
from app.common.errors import (
    UNAUTHORIZED,
    INVALID_TOKEN,
    MISSING_REQUIRED_FIELDS,
    POST_NOT_FOUND,
    COMMENT_NOT_FOUND,
    INTERNAL_SERVER_ERROR,
)
from app.common.auth import parse_bearer_token
from app.models import users_model, posts_model, comments_model


def _require_user_id(authorization: str | None) -> int | None:
    token = parse_bearer_token(authorization)
    if not token:
        return None
    return users_model.get_user_id_by_token(token)


def list_comments(authorization: str | None, post_id: int) -> JSONResponse:
    try:
        user_id = _require_user_id(authorization)
        if user_id is None:
            return unauthorized(UNAUTHORIZED.message)

        post = posts_model.find_post_by_id(post_id)
        if post is None:
            return not_found(POST_NOT_FOUND.message)

        data = comments_model.list_comments(post_id=post_id)
        return ok("read_comments_success", data)

    except Exception:
        return server_error(INTERNAL_SERVER_ERROR.message)


def create_comment(authorization: str | None, post_id: int, payload: dict) -> JSONResponse:
    try:
        user_id = _require_user_id(authorization)
        if user_id is None:
            return unauthorized(UNAUTHORIZED.message)

        post = posts_model.find_post_by_id(post_id)
        if post is None:
            return not_found(POST_NOT_FOUND.message)

        content = payload.get("content")
        if not content:
            return bad_request(MISSING_REQUIRED_FIELDS.message)

        comment = comments_model.create_comment(post_id=post_id, author_id=user_id, content=content)
        return created("comment_created", {"comment_id": comment["id"]})

    except Exception:
        return server_error(INTERNAL_SERVER_ERROR.message)


def delete_comment(authorization: str | None, post_id: int, comment_id: int) -> JSONResponse:
    try:
        user_id = _require_user_id(authorization)
        if user_id is None:
            return unauthorized(UNAUTHORIZED.message)

        post = posts_model.find_post_by_id(post_id)
        if post is None:
            return not_found(POST_NOT_FOUND.message)

        comment = comments_model.find_comment_by_id(comment_id)
        if comment is None or comment["post_id"] != post_id:
            return not_found(COMMENT_NOT_FOUND.message)

        comments_model.delete_comment(comment_id)
        return ok("comment_deleted", {"comment_id": comment_id})

    except Exception:
        return server_error(INTERNAL_SERVER_ERROR.message)
