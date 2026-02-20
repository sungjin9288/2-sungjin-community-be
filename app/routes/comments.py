from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.common.deps import get_current_user_id_optional, require_user_id
from app.controllers import comments_controller

router = APIRouter(prefix="/posts/{post_id}/comments", tags=["comments"])


class CommentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500, description="댓글 내용")


@router.get("")
def list_comments(
    post_id: int,
    user_id: int | None = Depends(get_current_user_id_optional),
):
    return comments_controller.list_comments(post_id, user_id)


@router.post("")
def create_comment(post_id: int, payload: CommentRequest, request: Request):
    user_id = require_user_id(request)
    return comments_controller.create_comment(user_id, post_id, {"content": payload.content})


@router.put("/{comment_id}")
def update_comment(post_id: int, comment_id: int, payload: CommentRequest, request: Request):
    user_id = require_user_id(request)
    return comments_controller.update_comment(user_id, post_id, comment_id, {"content": payload.content})


@router.delete("/{comment_id}")
def delete_comment(post_id: int, comment_id: int, request: Request):
    user_id = require_user_id(request)
    return comments_controller.delete_comment(user_id, post_id, comment_id)