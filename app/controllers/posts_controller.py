import re

from fastapi.responses import JSONResponse

from app.common.exceptions import (
    BusinessException,
    ErrorCode,
    ForbiddenError,
    InvalidPagingParamsError,
    InvalidRequestFormatError,
    MissingRequiredFieldsError,
    PostNotFoundError,
)
from app.common.responses import created, ok
from app.models import posts_model

ALLOWED_SORTS = {"latest", "hot", "discussed"}
TAG_PATTERN = re.compile(r"^[0-9A-Za-z가-힣_-]+$")


def _validate_title(title: str) -> None:
    if len(title) > 50:
        raise BusinessException(
            ErrorCode.INVALID_REQUEST_FORMAT,
            "제목은 최대 50자까지 작성 가능합니다.",
        )


def _normalize_single_tag(raw_tag: str) -> str:
    normalized = (raw_tag or "").strip().lower()
    if not normalized:
        raise InvalidRequestFormatError("태그는 빈 문자열일 수 없습니다.")
    if len(normalized) > 15:
        raise InvalidRequestFormatError("태그는 최대 15자까지 가능합니다.")
    if not TAG_PATTERN.match(normalized):
        raise InvalidRequestFormatError("태그는 한글, 영문, 숫자, _, - 만 사용할 수 있습니다.")
    return normalized


def _normalize_tags(tags: list[str]) -> list[str]:
    if len(tags) > 5:
        raise InvalidRequestFormatError("태그는 최대 5개까지 등록할 수 있습니다.")

    deduped: list[str] = []
    seen = set()
    for tag in tags:
        normalized = _normalize_single_tag(tag)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    if len(deduped) > 5:
        raise InvalidRequestFormatError("태그는 최대 5개까지 등록할 수 있습니다.")
    return deduped


def list_posts(
    page: int = 1,
    limit: int = 10,
    current_user_id: int | None = None,
    sort: str = "latest",
    tag: str | None = None,
) -> JSONResponse:
    if page < 1:
        raise InvalidPagingParamsError()
    if not (1 <= limit <= 50):
        raise InvalidPagingParamsError()
    if sort not in ALLOWED_SORTS:
        raise InvalidRequestFormatError("sort는 latest, hot, discussed 중 하나여야 합니다.")

    normalized_tag = _normalize_single_tag(tag) if tag else None
    data = posts_model.list_posts(page, limit, current_user_id, sort=sort, tag=normalized_tag)
    return ok(message="read_posts_success", data=data)


def create_post(
    user_id: int,
    title: str,
    content: str,
    image_url: str | None = None,
    tags: list[str] | None = None,
) -> JSONResponse:
    title = (title or "").strip()
    content = (content or "").strip()

    if not title or not content:
        raise MissingRequiredFieldsError("제목, 내용은 모두 작성해주세요.")

    _validate_title(title)
    normalized_tags = _normalize_tags(tags or [])

    post = posts_model.create_post(user_id, title, content, image_url, tags=normalized_tags)
    return created(message="post_created", data=post)


def get_post(post_id: int, current_user_id: int | None = None) -> JSONResponse:
    post = posts_model.find_post(post_id, current_user_id)
    if not post:
        raise PostNotFoundError()

    posts_model.increment_views(post_id)
    post["views"] = post.get("views", 0) + 1
    post["view_count"] = post.get("views")
    return ok(message="read_detail_success", data=post)


def update_post(
    user_id: int,
    post_id: int,
    title: str,
    content: str,
    image_url: str | None = None,
    tags: list[str] | None = None,
) -> JSONResponse:
    post = posts_model.find_post(post_id)
    if not post:
        raise PostNotFoundError()

    if post["user_id"] != user_id:
        raise ForbiddenError("게시글 수정 권한이 없습니다.")

    title = (title or "").strip()
    content = (content or "").strip()
    if not title or not content:
        raise MissingRequiredFieldsError("제목, 내용은 모두 작성해주세요.")

    _validate_title(title)
    normalized_tags = _normalize_tags(tags) if tags is not None else None
    updated = posts_model.update_post(post_id, title, content, image_url, tags=normalized_tags)
    if not updated:
        raise PostNotFoundError()
    return ok(message="post_updated", data=updated)


def delete_post(user_id: int, post_id: int) -> JSONResponse:
    post = posts_model.find_post(post_id)
    if not post:
        raise PostNotFoundError()
    if post["user_id"] != user_id:
        raise ForbiddenError("게시글 삭제 권한이 없습니다.")

    posts_model.delete_post(post_id)
    return ok(message="post_deleted", data=None)


def like_post(user_id: int, post_id: int) -> JSONResponse:
    if not posts_model.find_post(post_id):
        raise PostNotFoundError()

    if posts_model.is_liked(user_id, post_id):
        raise BusinessException(ErrorCode.INVALID_REQUEST_FORMAT, "이미 좋아요를 눌렀습니다.")

    created_like = posts_model.add_like(user_id, post_id)
    if not created_like:
        raise BusinessException(ErrorCode.INVALID_REQUEST_FORMAT, "이미 좋아요를 눌렀습니다.")
    return created(
        message="like_created",
        data={"likes_count": posts_model.get_like_count(post_id)},
    )


def unlike_post(user_id: int, post_id: int) -> JSONResponse:
    if not posts_model.find_post(post_id):
        raise PostNotFoundError()

    posts_model.remove_like(user_id, post_id)
    return ok(
        message="like_deleted",
        data={"likes_count": posts_model.get_like_count(post_id)},
    )


def get_trending(
    days: int = 7,
    limit: int = 5,
    current_user_id: int | None = None,
) -> JSONResponse:
    if not (1 <= days <= 30):
        raise InvalidRequestFormatError("days는 1~30 사이여야 합니다.")
    if not (1 <= limit <= 20):
        raise InvalidRequestFormatError("limit은 1~20 사이여야 합니다.")

    data = posts_model.get_trending(days=days, limit=limit, current_user_id=current_user_id)
    return ok(message="read_trending_success", data=data)
