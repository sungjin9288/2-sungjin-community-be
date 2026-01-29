from fastapi.responses import JSONResponse
from app.common.responses import ok, created

from app.common.exceptions import (
    BusinessException, ErrorCode,
    MissingRequiredFieldsError, PostNotFoundError,
    ForbiddenError, InvalidPagingParamsError,
    InvalidRequestFormatError
)
from app.models import posts_model


def _validate_title(title: str) -> None:

    if len(title) > 26:
        raise BusinessException(
            ErrorCode.INVALID_REQUEST_FORMAT,
            "제목은 최대 26자까지 작성 가능합니다."
        )


def list_posts(page: int = 1, limit: int = 10, current_user_id: int = None) -> JSONResponse:
    if page < 1:
        raise InvalidPagingParamsError()
    if not (1 <= limit <= 50):
        raise InvalidPagingParamsError()

    data = posts_model.list_posts(page, limit, current_user_id)
    return ok(message="read_posts_success", data=data)


def create_post(user_id: int, payload: dict) -> JSONResponse:
    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    image_url = payload.get("image_url")

 
    if not title or not content:
        raise MissingRequiredFieldsError("제목, 내용을 모두 작성해주세요")

    _validate_title(title)


    post = posts_model.create_post(user_id, title, content, image_url)
    
    data = post.copy()
    data["likes_count"] = posts_model.get_like_count(post["id"])
    
    return created(message="post_created", data=data)


def get_post(post_id: int, current_user_id: int = None) -> JSONResponse:
    post = posts_model.find_post(post_id, current_user_id)
    if not post:
        raise PostNotFoundError()

    posts_model.increment_views(post_id)

    # find_post에서 이미 모든 통계와 상태를 포함
    return ok(message="read_detail_success", data=post)


def update_post(user_id: int, post_id: int, payload: dict) -> JSONResponse:
    post = posts_model.find_post(post_id)
    if not post:
        raise PostNotFoundError()
    

    if post["user_id"] != user_id:
        raise ForbiddenError("게시글 수정 권한이 없습니다.")

    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    image_url = payload.get("image_url")

    if not title or not content:
        raise MissingRequiredFieldsError("제목, 내용을 모두 작성해주세요")

    _validate_title(title)


    updated = posts_model.update_post(post_id, title, content, image_url)
    if not updated:
        raise PostNotFoundError()

    data = updated.copy()
    data["likes_count"] = posts_model.get_like_count(post_id)
    
    return ok(message="post_updated", data=data)


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

    posts_model.add_like(user_id, post_id)
    
    return created(
        message="like_created",
        data={"likes_count": posts_model.get_like_count(post_id)}
    )

def unlike_post(user_id: int, post_id: int) -> JSONResponse:
    if not posts_model.find_post(post_id):
        raise PostNotFoundError()

    # 좋아요 여부 확인 (기획서에 없으면 생략 가능하지만 안전하게)
    if not posts_model.is_liked(user_id, post_id):
         pass

    posts_model.remove_like(user_id, post_id)
    
    return ok(
        message="like_deleted",
        data={"likes_count": posts_model.get_like_count(post_id)}
    )