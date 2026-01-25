from fastapi import APIRouter, Response, status
from pydantic import BaseModel, EmailStr

from app.controllers import auth_controller
from app.common import responses, exceptions
from app.common.deps import get_current_user_id

router = APIRouter(prefix="/auth", tags=["auth"])


# ==================== DTO 정의 ====================

class SignupRequest(BaseModel):

    email: EmailStr
    password: str
    nickname: str


class LoginRequest(BaseModel):

    email: EmailStr
    password: str


class CheckEmailRequest(BaseModel):

    email: EmailStr


# ==================== 라우트 ====================

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest):

    try:
        result = auth_controller.signup(
            email=payload.email,
            password=payload.password,
            nickname=payload.nickname
        )
        return responses.success(result)
    except exceptions.EmailAlreadyExistsError as e:
        return responses.error(e.error_code, e.message, e.status_code)
    except exceptions.InvalidPasswordError as e:
        return responses.error(e.error_code, e.message, e.status_code)


@router.post("/login")
async def login(payload: LoginRequest, response: Response):

    try:
        result = auth_controller.login(
            email=payload.email,
            password=payload.password
        )
        
        # 세션 쿠키 설정
        response.set_cookie(
            key="session_id",
            value=result["session_id"],
            httponly=True,
            samesite="lax",
            secure=False  # 개발 환경
        )
        
        return responses.success({"message": "login_success"})
    except exceptions.InvalidCredentialsError as e:
        return responses.error(e.error_code, e.message, e.status_code)


@router.post("/logout")
async def logout(response: Response, user_id: int = get_current_user_id):

    # 세션 쿠키 삭제
    response.delete_cookie(key="session_id")
    return responses.success({"message": "logout_success"})


@router.post("/check-email")
async def check_email(payload: CheckEmailRequest):
    try:
        result = auth_controller.check_email(email=payload.email)
        return responses.success(result)
    except exceptions.EmailAlreadyExistsError as e:
        return responses.error(e.error_code, e.message, e.status_code)