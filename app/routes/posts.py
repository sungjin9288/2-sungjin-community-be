from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.common.deps import get_current_user_id_optional, require_user_id
from app.controllers import posts_controller

router = APIRouter(prefix="/posts", tags=["posts"])


class PostCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    image_url: str | None = None
    tags: list[str] = Field(default_factory=list)


class PostUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    image_url: str | None = None
    tags: list[str] | None = None


@router.get("")
def list_posts(
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    limit: int = Query(10, ge=1, le=50, description="페이지당 개수 (1~50)"),
    sort: str = Query("latest", description="정렬 방식: latest | hot | discussed"),
    tag: str | None = Query(None, description="태그 필터"),
    user_id: int | None = Depends(get_current_user_id_optional),
):
    return posts_controller.list_posts(page, limit, user_id, sort=sort, tag=tag)


@router.get("/trending")
def get_trending(
    days: int = Query(7, ge=1, le=30, description="트렌드 집계 기간(일)"),
    limit: int = Query(5, ge=1, le=20, description="반환 개수"),
    user_id: int | None = Depends(get_current_user_id_optional),
):
    return posts_controller.get_trending(days=days, limit=limit, current_user_id=user_id)


@router.post("")
def create_post(payload: PostCreateRequest, request: Request):
    user_id = require_user_id(request)
    return posts_controller.create_post(
        user_id=user_id,
        title=payload.title,
        content=payload.content,
        image_url=payload.image_url,
        tags=payload.tags,
    )


@router.get("/{post_id}")
def get_post(post_id: int, user_id: int | None = Depends(get_current_user_id_optional)):
    return posts_controller.get_post(post_id, user_id)


@router.put("/{post_id}")
def update_post(post_id: int, payload: PostUpdateRequest, request: Request):
    user_id = require_user_id(request)
    return posts_controller.update_post(
        user_id=user_id,
        post_id=post_id,
        title=payload.title,
        content=payload.content,
        image_url=payload.image_url,
        tags=payload.tags,
    )


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
