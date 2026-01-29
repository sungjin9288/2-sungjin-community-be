from app.common.exceptions import (
    MissingRequiredFieldsError, 
    InvalidCredentialsError, 
    UnauthorizedError,
    EmailAlreadyExistsError,
    InvalidPasswordError
)
from app.common.security import verify_password, hash_password
from app.models import users_model


def signup(email: str, password: str, nickname: str) -> dict:
    """회원가입"""
    # 이메일 중복 확인
    if users_model.is_email_exists(email):
        raise EmailAlreadyExistsError()
    
    # 비밀번호 검증 (8자 이상)
    if len(password) < 8:
        raise InvalidPasswordError("비밀번호는 8자 이상이어야 합니다")
    
    # 비밀번호 해시화
    password_hash = hash_password(password)
    
    # 사용자 생성
    user = users_model.create_user(
        email=email,
        password_hash=password_hash,
        nickname=nickname
    )
    
    if not user:
        raise EmailAlreadyExistsError()
    
    return {
        "id": user["id"],
        "email": user["email"],
        "nickname": user["nickname"]
    }


def check_email(email: str) -> dict:
    """이메일 중복 확인"""
    if users_model.is_email_exists(email):
        raise EmailAlreadyExistsError()
    
    return {"available": True, "message": "사용 가능한 이메일입니다"}


def check_nickname(nickname: str) -> dict:
    """닉네임 중복 확인"""
    from app.common.exceptions import NicknameAlreadyExistsError
    if users_model.is_nickname_exists(nickname):
        raise NicknameAlreadyExistsError()
    
    return {"available": True, "message": "사용 가능한 닉네임입니다"}


def login(email: str, password: str) -> dict:
    """로그인"""
    if not email or not password:
        raise MissingRequiredFieldsError()

    user = users_model.find_user_by_email(email)
    
    if not user or not verify_password(password, user.get("password") or user.get("password_hash", "")):
        raise InvalidCredentialsError()

    session_id = users_model.create_session(user_id=user["id"])
    
    return {"session_id": session_id}


def logout(session_id: str | None) -> None:
    """로그아웃"""
    if not session_id:
        raise UnauthorizedError()

    users_model.delete_session(session_id)