from fastapi import APIRouter, Header, Query
from app.controllers import posts_controller

router = APIRouter()

@router.get("")
def list_posts(
    page: int = Query(default=1),
    limit: int = Query(default=10),
    authorization: str | None = Header(default=None),
):
    return posts_controller.list_posts(page, limit, authorization)

@router.get("/{post_id}")
def read_post(post_id: int, authorization: str | None = Header(default=None)):
    return posts_controller.read_post(post_id, authorization)

@router.post("")
def create_post(payload: dict, authorization: str | None = Header(default=None)):
    return posts_controller.create_post(payload, authorization)

@router.put("/{post_id}")
def update_post(post_id: int, payload: dict, authorization: str | None = Header(default=None)):
    return posts_controller.update_post(post_id, payload, authorization)

@router.delete("/{post_id}")
def delete_post(post_id: int, authorization: str | None = Header(default=None)):
    return posts_controller.delete_post(post_id, authorization)
