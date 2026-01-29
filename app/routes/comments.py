
from fastapi import APIRouter, Request, Depends
from app.controllers import comments_controller
from app.common.deps import require_user_id, get_current_user_id_optional

router = APIRouter(prefix="/posts/{post_id}/comments", tags=["comments"])


@router.get("")
def list_comments(
    post_id: int,
    user_id: int | None = Depends(get_current_user_id_optional)
):

    return comments_controller.list_comments(post_id, user_id)


@router.post("")
def create_comment(post_id: int, payload: dict, request: Request):

    user_id = require_user_id(request)
    return comments_controller.create_comment(user_id, post_id, payload)


@router.put("/{comment_id}")
def update_comment(post_id: int, comment_id: int, payload: dict, request: Request):

    user_id = require_user_id(request)
    return comments_controller.update_comment(user_id, post_id, comment_id, payload)


@router.delete("/{comment_id}")
def delete_comment(post_id: int, comment_id: int, request: Request):

    user_id = require_user_id(request)
    return comments_controller.delete_comment(user_id, post_id, comment_id)