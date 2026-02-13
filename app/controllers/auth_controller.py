import os

from app.common.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidPasswordError,
    InvalidRequestFormatError,
    MissingRequiredFieldsError,
    NicknameAlreadyExistsError,
)
from app.common.jwt_tokens import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token
from app.common.security import hash_password, verify_password
from app.models import users_model

REFRESH_TOKEN_TTL_DAYS = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "14"))


def signup(email: str, password: str, nickname: str) -> dict:
    if users_model.is_email_exists(email):
        raise EmailAlreadyExistsError()
    if users_model.is_nickname_exists(nickname):
        raise NicknameAlreadyExistsError()
    if len(password) < 8:
        raise InvalidPasswordError("비밀번호는 8자 이상이어야 합니다.")

    user = users_model.create_user(
        email=email,
        password_hash=hash_password(password),
        nickname=nickname,
    )
    if not user:
        raise EmailAlreadyExistsError()

    return {
        "id": user["id"],
        "email": user["email"],
        "nickname": user["nickname"],
    }


def check_email(email: str) -> dict:
    if users_model.is_email_exists(email):
        raise EmailAlreadyExistsError()
    return {"available": True, "message": "사용 가능한 이메일입니다."}


def check_nickname(nickname: str) -> dict:
    if users_model.is_nickname_exists(nickname):
        raise NicknameAlreadyExistsError()
    return {"available": True, "message": "사용 가능한 닉네임입니다."}


def login(email: str, password: str) -> dict:
    if not email or not password:
        raise MissingRequiredFieldsError()

    user = users_model.find_user_by_email(email)
    if not user:
        raise InvalidCredentialsError()
    if not verify_password(password, user["password"]):
        raise InvalidCredentialsError()

    access_token = create_access_token(user["id"])
    refresh_token = users_model.create_session(user_id=user["id"], ttl_days=REFRESH_TOKEN_TTL_DAYS)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def refresh(refresh_token: str) -> dict:
    if not refresh_token:
        raise MissingRequiredFieldsError("refresh_token이 필요합니다.")

    user_id = users_model.get_user_id_by_session(refresh_token)
    if not user_id:
        raise InvalidRequestFormatError("유효하지 않거나 만료된 refresh_token 입니다.")

    users_model.delete_session(refresh_token)
    new_refresh_token = users_model.create_session(user_id=user_id, ttl_days=REFRESH_TOKEN_TTL_DAYS)
    new_access_token = create_access_token(user_id)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def logout(refresh_token: str | None) -> None:
    if refresh_token:
        users_model.delete_session(refresh_token)
