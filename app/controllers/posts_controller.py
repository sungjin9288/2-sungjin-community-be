
from fastapi.responses import JSONResponse
from app.common.responses import ok, created
from app.common.exceptions import BusinessException, ErrorCodes
from app.models import posts_model


def _validate_title(title: str) -> None:
    
    if len(title) > 100:
        raise BusinessException(
            "invalid_title_policy",
            "제목은 최대 100자까지 가능합니다.",
            422,
            data={"max_length": 100}
        )


def _validate_content(content: str) -> None:
   
    if len(content) > 10000:
        raise BusinessException(
            "invalid_content_policy",
            "내용은 최대 10,000자까지 가능합니다.",
            422,
            data={"max_length": 10000}
        )


def list_posts(page: int = 1, limit: int = 10) -> JSONResponse:

  
    if page < 1:
        raise BusinessException(*ErrorCodes.INVALID_PAGING_PARAMS)
    if not (1 <= limit <= 50):
        raise BusinessException(*ErrorCodes.INVALID_PAGING_PARAMS)

    data = posts_model.list_posts(page, limit)
    return ok(message="read_posts_success", data=data)


def create_post(user_id: int, payload: dict) -> JSONResponse:
 
    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    image_url = payload.get("image_url")

    if not title or not content:
        raise BusinessException(*ErrorCodes.MISSING_REQUIRED_FIELDS)

    
    _validate_title(title)
    _validate_content(content)

    post = posts_model.create_post(user_id, title, content, image_url)
    
    data = post.copy()
    data["likes_count"] = posts_model.get_like_count(post["id"])
    
    return created(message="post_created", data=data)


def get_post(post_id: int) -> JSONResponse:
 
    post = posts_model.find_post(post_id)
    if not post:
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)

 
    posts_model.increment_views(post_id)

    data = post.copy()
    data["likes_count"] = posts_model.get_like_count(post_id)
    
    return ok(message="read_detail_success", data=data)


def update_post(user_id: int, post_id: int, payload: dict) -> JSONResponse:
  
    post = posts_model.find_post(post_id)
    if not post:
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)
    
   
    if post["user_id"] != user_id:
        raise BusinessException(*ErrorCodes.PERMISSION_DENIED)

    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    image_url = payload.get("image_url")

    if not title or not content:
        raise BusinessException(*ErrorCodes.MISSING_REQUIRED_FIELDS)

  
    _validate_title(title)
    _validate_content(content)

    updated = posts_model.update_post(post_id, title, content, image_url)
    if not updated:
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)

    data = updated.copy()
    data["likes_count"] = posts_model.get_like_count(post_id)
    
    return ok(message="post_updated", data=data)


def delete_post(user_id: int, post_id: int) -> JSONResponse:

    post = posts_model.find_post(post_id)
    if not post:
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)
    
    if post["user_id"] != user_id:
        raise BusinessException(*ErrorCodes.PERMISSION_DENIED)

    posts_model.delete_post(post_id)
    return ok(message="post_deleted", data=None)


def like_post(user_id: int, post_id: int) -> JSONResponse:

    if not posts_model.find_post(post_id):
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)

    if posts_model.is_liked(user_id, post_id):
        raise BusinessException(*ErrorCodes.LIKE_ALREADY_EXISTS)

    posts_model.add_like(user_id, post_id)
    
    return created(
        message="like_created",
        data={"likes_count": posts_model.get_like_count(post_id)}
    )


def unlike_post(user_id: int, post_id: int) -> JSONResponse:

    if not posts_model.find_post(post_id):
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)

    if not posts_model.is_liked(user_id, post_id):
        raise BusinessException(*ErrorCodes.LIKE_NOT_FOUND)

    posts_model.remove_like(user_id, post_id)
    
    return ok(
        message="like_deleted",
        data={"likes_count": posts_model.get_like_count(post_id)}
    )