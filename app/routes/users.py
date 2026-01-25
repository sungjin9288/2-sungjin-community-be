from fastapi import APIRouter, status
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
async def get_my_profile(user_id: int = get_current_user_id):

    try:
        result = users_controller.get_user_by_id(user_id)
        return responses.success(result)
    except exceptions.UserNotFoundError as e:
        return responses.error(e.error_code, e.message, e.status_code)


@router.patch("/me")  # PUT → PATCH
async def update_profile(
    payload: UpdateProfileRequest,
    user_id: int = get_current_user_id
):
    try:
        # None이 아닌 필드만 업데이트
        update_data = {}
        if payload.nickname is not None:
            update_data['nickname'] = payload.nickname
        if payload.profile_image_url is not None:
            update_data['profile_image_url'] = payload.profile_image_url
        
        result = users_controller.update_profile(user_id, **update_data)
        return responses.success(result)
    except exceptions.UserNotFoundError as e:
        return responses.error(e.error_code, e.message, e.status_code)
    except exceptions.NicknameAlreadyExistsError as e:
        return responses.error(e.error_code, e.message, e.status_code)


@router.patch("/me/password")  # PUT → PATCH
async def update_password(
    payload: UpdatePasswordRequest,
    user_id: int = get_current_user_id
):
    try:
        result = users_controller.update_password(
            user_id=user_id,
            current_password=payload.current_password,
            new_password=payload.new_password
        )
        return responses.success(result)
    except exceptions.InvalidCredentialsError as e:
        return responses.error(e.error_code, e.message, e.status_code)
    except exceptions.InvalidPasswordError as e:
        return responses.error(e.error_code, e.message, e.status_code)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(user_id: int = get_current_user_id):
    try:
        users_controller.delete_user(user_id)
        return None  
    except exceptions.UserNotFoundError as e:
        return responses.error(e.error_code, e.message, e.status_code)