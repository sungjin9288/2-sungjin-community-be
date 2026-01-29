from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from typing import Optional

from app.controllers import users_controller
from app.common import responses, exceptions
from app.common.deps import get_current_user_id

router = APIRouter(prefix="/users", tags=["users"])


# ==================== DTO 정의 ====================

class UpdateProfileRequest(BaseModel):

    nickname: Optional[str] = None
    profile_image_url: Optional[str] = None


class UpdatePasswordRequest(BaseModel):

    current_password: str
    new_password: str


# ==================== 라우트 ====================

@router.get("/me")
async def get_my_profile(user_id: int = Depends(get_current_user_id)):

    try:
        # Controller returns JSONResponse directly
        return users_controller.get_me(user_id)
    except exceptions.UserNotFoundError as e:
        return responses.fail(e.status_code, e.detail)


@router.patch("/me")
async def update_profile(
    payload: UpdateProfileRequest,
    user_id: int = Depends(get_current_user_id)
):
    try:
        # Controller expects dict with 'nickname', 'profile_image_url'
        return users_controller.update_me(user_id, payload.dict(exclude_unset=True))
    except exceptions.UserNotFoundError as e:
        return responses.fail(e.status_code, e.detail)
    except exceptions.NicknameAlreadyExistsError as e:
        return responses.fail(e.status_code, e.detail)


@router.patch("/me/password")
async def update_password(
    payload: UpdatePasswordRequest,
    user_id: int = Depends(get_current_user_id)
):
    try:
        # Controller expects 'old_password', 'new_password'
        controller_payload = {
            "old_password": payload.current_password,
            "new_password": payload.new_password
        }
        return users_controller.update_password(user_id, controller_payload)
    except exceptions.InvalidCredentialsError as e:
        return responses.fail(e.status_code, e.detail)
    except exceptions.InvalidPasswordError as e:
        return responses.fail(e.status_code, e.detail)
    except exceptions.UserNotFoundError as e:
        return responses.fail(e.status_code, e.detail)


@router.delete("/me")
async def delete_account(user_id: int = Depends(get_current_user_id)):
    try:
        return users_controller.withdraw(user_id)
    except exceptions.UserNotFoundError as e:
        return responses.fail(e.status_code, e.detail)