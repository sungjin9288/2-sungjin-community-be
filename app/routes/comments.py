from fastapi import APIRouter, Header
from app.controllers import comments_controller

router = APIRouter()

@router.get("/posts/{post_id}/comments")
def list_comments(post_id: int, authorization: str | None = Header(default=None)):
    return comments_controller.list_comments(post_id, authorization)

@router.post("/posts/{post_id}/comments")
def create_comment(post_id: int, payload: dict, authorization: str | None = Header(default=None)):
    return comments_controller.create_comment(post_id, payload, authorization)

@router.delete("/posts/{post_id}/comments/{comment_id}")
def delete_comment(post_id: int, comment_id: int, authorization: str | None = Header(default=None)):
    return comments_controller.delete_comment(post_id, comment_id, authorization)
