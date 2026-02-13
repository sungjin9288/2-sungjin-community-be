from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.common.deps import get_current_user_id
from app.controllers import users_controller

router = APIRouter(prefix="/users", tags=["users"])


class UpdateProfileRequest(BaseModel):
    nickname: Optional[str] = Field(default=None, min_length=1, max_length=10)
    profile_image_url: Optional[str] = None


class UpdatePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


@router.get("/me")
async def get_my_profile(user_id: int = Depends(get_current_user_id)):
    return users_controller.get_me(user_id)


@router.patch("/me")
async def update_profile(
    payload: UpdateProfileRequest,
    user_id: int = Depends(get_current_user_id),
):
    return users_controller.update_me(user_id, payload.model_dump(exclude_unset=True))


@router.patch("/me/password")
async def update_password(
    payload: UpdatePasswordRequest,
    user_id: int = Depends(get_current_user_id),
):
    controller_payload = {
        "old_password": payload.current_password,
        "new_password": payload.new_password,
    }
    return users_controller.update_password(user_id, controller_payload)


@router.delete("/me")
async def delete_account(user_id: int = Depends(get_current_user_id)):
    return users_controller.withdraw(user_id)
