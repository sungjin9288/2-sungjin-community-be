from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.common.deps import get_current_user_id, require_user_id
from app.controllers import messages_controller

router = APIRouter(prefix="/messages", tags=["messages"])


class DirectMessageRequest(BaseModel):
    recipient_id: int = Field(..., ge=1)
    content: str = Field(..., min_length=1, max_length=1000)


@router.get("/users")
def search_users(
    query: str | None = Query(None, description="닉네임 또는 이메일 검색어"),
    user_id: int = Depends(get_current_user_id),
):
    return messages_controller.search_users(user_id=user_id, query=query)


@router.get("/conversations")
def list_conversations(
    query: str | None = Query(None, description="대화 상대/마지막 메시지 검색"),
    user_id: int = Depends(get_current_user_id),
):
    return messages_controller.list_conversations(user_id=user_id, query=query)


@router.get("/unread-count")
def unread_count(user_id: int = Depends(get_current_user_id)):
    return messages_controller.unread_count(user_id=user_id)


@router.get("/with/{other_user_id}")
def list_messages(other_user_id: int, user_id: int = Depends(get_current_user_id)):
    return messages_controller.list_messages(user_id=user_id, other_user_id=other_user_id)


@router.post("")
def send_message(payload: DirectMessageRequest, request: Request):
    user_id = require_user_id(request)
    return messages_controller.send_message(
        user_id=user_id,
        recipient_id=payload.recipient_id,
        content=payload.content,
    )
