
from fastapi import APIRouter, Request
from app.controllers import comments_controller
from app.common.deps import require_user_id

router = APIRouter(prefix="/posts/{post_id}/comments", tags=["comments"])


@router.get("")
def list_comments(post_id: int):

    return comments_controller.list_comments(post_id)


@router.post("")
def create_comment(post_id: int, payload: dict, request: Request):

    user_id = require_user_id(request)
    return comments_controller.create_comment(user_id, post_id, payload)


@router.delete("/{comment_id}")
def delete_comment(post_id: int, comment_id: int, request: Request):

    user_id = require_user_id(request)
    return comments_controller.delete_comment(user_id, post_id, comment_id)