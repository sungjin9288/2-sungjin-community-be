from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from app.controllers import auth_controller
from app.common import responses

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
    # BusinessException은 HTTPException을 상속하므로 자동으로 처리됨
    result = auth_controller.signup(
        email=payload.email,
        password=payload.password,
        nickname=payload.nickname
    )
    return responses.created("signup_success", result)


@router.post("/login")
async def login(payload: LoginRequest):
    result = auth_controller.login(
        email=payload.email,
        password=payload.password
    )
    
    # ✅ JSONResponse를 직접 생성하고 쿠키 설정
    response = JSONResponse(
        content={"message": "login_success", "data": None}
    )
    
    # 세션 쿠키 설정
    response.set_cookie(
        key="session_id",
        value=result["session_id"],
        httponly=True,
        samesite="lax",
        secure=False,  # 개발 환경
        path="/",  # 모든 경로에서 쿠키 사용
    )
    
    return response


@router.post("/logout")
async def logout():
    # ✅ JSONResponse 생성 후 쿠키 삭제
    response = JSONResponse(
        content={"message": "logout_success", "data": None}
    )
    response.delete_cookie(key="session_id", path="/")
    return response


@router.post("/check-email")
async def check_email(payload: CheckEmailRequest):
    result = auth_controller.check_email(email=payload.email)
    return responses.ok("email_available", result)


class CheckNicknameRequest(BaseModel):
    nickname: str


@router.post("/check-nickname")
async def check_nickname(payload: CheckNicknameRequest):
    result = auth_controller.check_nickname(nickname=payload.nickname)
    return responses.ok("nickname_available", result)
