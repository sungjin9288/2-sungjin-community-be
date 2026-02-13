import re

from fastapi.responses import JSONResponse

from app.common.exceptions import (
    BusinessException,
    EmailAlreadyExistsError,
    ErrorCode,
    InvalidCredentialsError,
    InvalidEmailFormatError,
    InvalidPasswordError,
    MissingRequiredFieldsError,
    NicknameAlreadyExistsError,
    UserNotFoundError,
)
from app.common.responses import created, ok
from app.common.security import hash_password, verify_password
from app.models import users_model

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,20}$")


def _validate_email(email: str) -> None:
    if not EMAIL_PATTERN.match(email):
        raise InvalidEmailFormatError("올바른 이메일 주소 형식을 입력해주세요.")


def _validate_nickname(nickname: str) -> None:
    if " " in nickname:
        raise BusinessException(
            ErrorCode.INVALID_REQUEST_FORMAT,
            "닉네임에 공백을 사용할 수 없습니다.",
        )
    if len(nickname) < 1:
        raise MissingRequiredFieldsError("닉네임을 입력해주세요.")
    if len(nickname) > 10:
        raise BusinessException(
            ErrorCode.INVALID_REQUEST_FORMAT,
            "닉네임은 최대 10자까지 작성 가능합니다.",
        )


def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise BusinessException(
            ErrorCode.PASSWORD_TOO_SHORT,
            "비밀번호는 8자 이상, 20자 이하이며, 대문자/소문자/숫자/특수문자를 포함해야 합니다.",
        )
    if len(password) > 20:
        raise BusinessException(
            ErrorCode.PASSWORD_TOO_LONG,
            "비밀번호는 8자 이상, 20자 이하이며, 대문자/소문자/숫자/특수문자를 포함해야 합니다.",
        )
    if not PASSWORD_PATTERN.match(password):
        raise InvalidPasswordError(
            "비밀번호는 대문자, 소문자, 숫자, 특수문자를 각각 최소 1개 포함해야 합니다.",
        )


def check_email(payload: dict) -> JSONResponse:
    email = (payload.get("email") or "").strip()
    if not email:
        raise MissingRequiredFieldsError("이메일을 입력해주세요.")
    _validate_email(email)

    if users_model.is_email_exists(email):
        return ok(message="email_already_exists", data={"available": False, "email": email})
    return ok(message="email_available", data={"available": True, "email": email})


def signup(payload: dict) -> JSONResponse:
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""
    nickname = (payload.get("nickname") or "").strip()
    profile_image_url = payload.get("profile_image_url")

    if not email:
        raise MissingRequiredFieldsError("이메일을 입력해주세요.")
    if not password:
        raise MissingRequiredFieldsError("비밀번호를 입력해주세요.")
    if not nickname:
        raise MissingRequiredFieldsError("닉네임을 입력해주세요.")

    _validate_email(email)
    _validate_nickname(nickname)
    _validate_password(password)

    if users_model.is_email_exists(email):
        raise EmailAlreadyExistsError("중복된 이메일입니다.")
    if users_model.is_nickname_exists(nickname):
        raise NicknameAlreadyExistsError("중복된 닉네임입니다.")

    created_user = users_model.create_user(
        email=email,
        password_hash=hash_password(password),
        nickname=nickname,
        profile_image_url=profile_image_url,
    )
    if not created_user:
        raise EmailAlreadyExistsError()
    return created(message="signup_success", data=None)


def get_me(user_id: int) -> JSONResponse:
    user = users_model.get_user_by_id(user_id)
    if not user:
        raise UserNotFoundError()

    data = {
        "id": user["id"],
        "email": user["email"],
        "nickname": user["nickname"],
        "profile_image_url": user.get("profile_image_url"),
    }
    return ok(message="read_me_success", data=data)


def update_me(user_id: int, payload: dict) -> JSONResponse:
    user = users_model.get_user_by_id(user_id)
    if not user:
        raise UserNotFoundError()

    update_fields = {}

    if "nickname" in payload:
        nickname = (payload.get("nickname") or "").strip()
        if not nickname:
            raise MissingRequiredFieldsError("닉네임을 입력해주세요.")
        _validate_nickname(nickname)
        if nickname != user["nickname"] and users_model.is_nickname_exists(nickname):
            raise NicknameAlreadyExistsError("중복된 닉네임입니다.")
        update_fields["nickname"] = nickname

    if "profile_image_url" in payload:
        update_fields["profile_image_url"] = payload.get("profile_image_url")

    if not update_fields:
        raise MissingRequiredFieldsError("수정할 항목이 없습니다.")

    updated = users_model.update_user(user_id, **update_fields)
    if not updated:
        raise UserNotFoundError()

    data = {
        "id": updated["id"],
        "email": updated["email"],
        "nickname": updated["nickname"],
        "profile_image_url": updated.get("profile_image_url"),
    }
    return ok(message="user_updated", data=data)


def update_password(user_id: int, payload: dict) -> JSONResponse:
    old_pw = payload.get("old_password") or ""
    new_pw = payload.get("new_password") or ""

    if not old_pw:
        raise MissingRequiredFieldsError("현재 비밀번호를 입력해주세요.")
    if not new_pw:
        raise MissingRequiredFieldsError("새 비밀번호를 입력해주세요.")

    user = users_model.get_user_by_id(user_id)
    if not user:
        raise UserNotFoundError()

    if not verify_password(old_pw, user["password"]):
        raise InvalidCredentialsError("현재 비밀번호가 일치하지 않습니다.")

    _validate_password(new_pw)

    users_model.update_user(user_id, password_hash=hash_password(new_pw))
    return ok(message="password_updated", data=None)


def withdraw(user_id: int) -> JSONResponse:
    user = users_model.get_user_by_id(user_id)
    if not user:
        raise UserNotFoundError()

    users_model.delete_user(user_id)
    return ok(message="user_deleted", data=None)
