from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.common.deps import get_current_user_id
from app.controllers import social_controller

router = APIRouter(tags=["social"])


class ReportRequest(BaseModel):
    target_type: str = Field(..., min_length=1)
    target_id: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)


@router.get("/blocks/users")
def list_blocks(user_id: int = Depends(get_current_user_id)):
    return social_controller.list_blocks(user_id=user_id)


@router.post("/blocks/users/{blocked_user_id}")
def create_block(blocked_user_id: int, user_id: int = Depends(get_current_user_id)):
    return social_controller.create_block(user_id=user_id, blocked_user_id=blocked_user_id)


@router.delete("/blocks/users/{blocked_user_id}")
def delete_block(blocked_user_id: int, user_id: int = Depends(get_current_user_id)):
    return social_controller.delete_block(user_id=user_id, blocked_user_id=blocked_user_id)


@router.post("/reports")
def create_report(payload: ReportRequest, user_id: int = Depends(get_current_user_id)):
    return social_controller.create_report(
        user_id=user_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=payload.reason,
        description=payload.description,
    )
