from fastapi.responses import JSONResponse
from app.common.responses import ok, created
from app.common.exceptions import BusinessException, ErrorCodes
from app.models import posts_model

def list_posts(page: int = 1, limit: int = 10) -> JSONResponse:
    data = posts_model.list_posts(page, limit)
    return ok("게시글 목록 조회 성공", data)

def create_post(user_id: int, payload: dict) -> JSONResponse:
    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    image_url = payload.get("image_url")
    
    if not title or not content:
        raise BusinessException(*ErrorCodes.MISSING_REQUIRED_FIELDS)

    post = posts_model.create_post(user_id, title, content, image_url)
    return created("게시글이 작성되었습니다.", post)

def get_post(post_id: int) -> JSONResponse:
    post = posts_model.find_post(post_id)
    if not post:
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)
    
    post["views"] += 1
    data = post.copy()
    data["likes_count"] = posts_model.get_like_count(post_id)
    
    return ok("게시글 상세 조회 성공", data)

def update_post(user_id: int, post_id: int, payload: dict) -> JSONResponse:
    post = posts_model.find_post(post_id)
    if not post:
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)
    if post["user_id"] != user_id:
        raise BusinessException(*ErrorCodes.FORBIDDEN)
        
    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    image_url = payload.get("image_url")
    
    updated = posts_model.update_post(post_id, title, content, image_url)
    return ok("게시글이 수정되었습니다.", updated)

def delete_post(user_id: int, post_id: int) -> JSONResponse:
    post = posts_model.find_post(post_id)
    if not post:
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)
    if post["user_id"] != user_id:
        raise BusinessException(*ErrorCodes.FORBIDDEN)
        
    posts_model.delete_post(post_id)
    return ok("게시글이 삭제되었습니다.")

def like_post(user_id: int, post_id: int) -> JSONResponse:
    if not posts_model.find_post(post_id):
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)
    posts_model.add_like(user_id, post_id)
    return ok("좋아요를 눌렀습니다.")

def unlike_post(user_id: int, post_id: int) -> JSONResponse:
    if not posts_model.find_post(post_id):
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)
    posts_model.remove_like(user_id, post_id)
    return ok("좋아요를 취소했습니다.")