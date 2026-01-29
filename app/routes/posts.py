from fastapi import APIRouter, Request, Query, Depends
from app.controllers import posts_controller
from app.common.deps import require_user_id, get_current_user_id_optional

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("")
def list_posts(
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    limit: int = Query(10, ge=1, le=50, description="페이지당 개수 (1~50)"),
    user_id: int | None = Depends(get_current_user_id_optional)
):

    return posts_controller.list_posts(page, limit, user_id)


@router.post("")
def create_post(payload: dict, request: Request):

    user_id = require_user_id(request)
    return posts_controller.create_post(user_id, payload)


@router.get("/{post_id}")
def get_post(
    post_id: int,
    user_id: int | None = Depends(get_current_user_id_optional)
):

    return posts_controller.get_post(post_id, user_id)


@router.put("/{post_id}")
def update_post(post_id: int, payload: dict, request: Request):

    user_id = require_user_id(request)
    return posts_controller.update_post(user_id, post_id, payload)


@router.delete("/{post_id}")
def delete_post(post_id: int, request: Request):
 
    user_id = require_user_id(request)
    return posts_controller.delete_post(user_id, post_id)


@router.post("/{post_id}/likes")
def like_post(post_id: int, request: Request):

    user_id = require_user_id(request)
    return posts_controller.like_post(user_id, post_id)


@router.delete("/{post_id}/likes")
def unlike_post(post_id: int, request: Request):
 
    user_id = require_user_id(request)
    return posts_controller.unlike_post(user_id, post_id)