from fastapi.responses import JSONResponse

from app.common.responses import ok, created, bad_request, unauthorized, not_found, server_error
from app.common.errors import (
    UNAUTHORIZED,
    INVALID_TOKEN,
    PAGE_INVALID,
    LIMIT_INVALID,
    TITLE_REQUIRED,
    CONTENT_REQUIRED,
    POST_NOT_FOUND,
    INTERNAL_SERVER_ERROR,
)
from app.common.auth import parse_bearer_token
from app.models import users_model, posts_model


def _require_user_id(authorization: str | None) -> int | None:
    token = parse_bearer_token(authorization)
    if not token:
        return None
    user_id = users_model.get_user_id_by_token(token)
    return user_id


def list_posts(authorization: str | None, page: int, limit: int) -> JSONResponse:
    try:
        user_id = _require_user_id(authorization)
        if user_id is None:
            return unauthorized(UNAUTHORIZED.message)

        if page < 1:
            return bad_request(PAGE_INVALID.message)
        if limit < 1 or limit > 50:
            return bad_request(LIMIT_INVALID.message)

        data = posts_model.list_posts(page=page, limit=limit)
        return ok("read_posts_success", data)

    except Exception:
        return server_error(INTERNAL_SERVER_ERROR.message)


def create_post(authorization: str | None, payload: dict) -> JSONResponse:
    try:
        user_id = _require_user_id(authorization)
        if user_id is None:
            return unauthorized(UNAUTHORIZED.message)

        title = payload.get("title")
        content = payload.get("content")
        image = payload.get("image")

        if not title:
            return bad_request(TITLE_REQUIRED.message)
        if not content:
            return bad_request(CONTENT_REQUIRED.message)

        post = posts_model.create_post(author_id=user_id, title=title, content=content, image=image)
        return created("post_created", {"post_id": post["id"]})

    except Exception:
        return server_error(INTERNAL_SERVER_ERROR.message)


def get_post_detail(authorization: str | None, post_id: int) -> JSONResponse:
    try:
        user_id = _require_user_id(authorization)
        if user_id is None:
            return unauthorized(UNAUTHORIZED.message)

        post = posts_model.find_post_by_id(post_id)
        if post is None:
            return not_found(POST_NOT_FOUND.message)

        return ok("read_detail_success", post)

    except Exception:
        return server_error(INTERNAL_SERVER_ERROR.message)


def update_post(authorization: str | None, post_id: int, payload: dict) -> JSONResponse:
    try:
        user_id = _require_user_id(authorization)
        if user_id is None:
            return unauthorized(UNAUTHORIZED.message)

        title = payload.get("title")
        content = payload.get("content")
        image = payload.get("image")

        updated = posts_model.update_post(post_id=post_id, title=title, content=content, image=image)
        if updated is None:
            return not_found(POST_NOT_FOUND.message)

        return ok("post_updated", {"post_id": post_id})

    except Exception:
        return server_error(INTERNAL_SERVER_ERROR.message)


def delete_post(authorization: str | None, post_id: int) -> JSONResponse:
    try:
        user_id = _require_user_id(authorization)
        if user_id is None:
            return unauthorized(UNAUTHORIZED.message)

        ok_deleted = posts_model.delete_post(post_id)
        if not ok_deleted:
            return not_found(POST_NOT_FOUND.message)

        return ok("post_deleted", {"post_id": post_id})

    except Exception:
        return server_error(INTERNAL_SERVER_ERROR.message)
