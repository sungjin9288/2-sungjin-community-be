from fastapi import APIRouter, status
from pydantic import BaseModel, EmailStr, Field

from app.common import responses
from app.controllers import auth_controller

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    nickname: str = Field(..., min_length=1, max_length=10)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CheckEmailRequest(BaseModel):
    email: EmailStr


class CheckNicknameRequest(BaseModel):
    nickname: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest):
    result = auth_controller.signup(
        email=payload.email,
        password=payload.password,
        nickname=payload.nickname,
    )
    return responses.created("signup_success", result)


@router.post("/login")
async def login(payload: LoginRequest):
    result = auth_controller.login(
        email=payload.email,
        password=payload.password,
    )
    return responses.ok("login_success", result)


@router.post("/refresh")
async def refresh(payload: RefreshRequest):
    result = auth_controller.refresh(payload.refresh_token)
    return responses.ok("refresh_success", result)


@router.post("/logout")
async def logout(payload: LogoutRequest | None = None):
    refresh_token = payload.refresh_token if payload else None
    auth_controller.logout(refresh_token)
    return responses.ok("logout_success", None)


@router.post("/check-email")
async def check_email(payload: CheckEmailRequest):
    result = auth_controller.check_email(email=payload.email)
    return responses.ok("email_available", result)


@router.post("/check-nickname")
async def check_nickname(payload: CheckNicknameRequest):
    result = auth_controller.check_nickname(nickname=payload.nickname)
    return responses.ok("nickname_available", result)
