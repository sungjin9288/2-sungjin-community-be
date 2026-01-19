
import re
from fastapi.responses import JSONResponse
from app.common.responses import ok, created, fail
from app.common.exceptions import BusinessException, ErrorCodes
from app.common.security import hash_password, verify_password
from app.models import users_model


def _validate_email(email: str) -> bool:
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def _validate_nickname(nickname: str) -> None:
   
    if len(nickname) < 2:
        raise BusinessException(
            "invalid_nickname_policy",
            "닉네임은 최소 2자 이상이어야 합니다.",
            422,
            data={"min_length": 2}
        )
    if len(nickname) > 20:
        raise BusinessException(
            "invalid_nickname_policy",
            "닉네임은 최대 20자까지 가능합니다.",
            422,
            data={"max_length": 20}
        )


def _validate_password(password: str) -> None:
    
    if len(password) < 6:
        raise BusinessException(
            "invalid_password_policy",
            "비밀번호는 최소 6자 이상이어야 합니다.",
            422,
            data={"reason": "too_short", "min_length": 6}
        )


def signup(payload: dict) -> JSONResponse:

    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""
    nickname = (payload.get("nickname") or "").strip()
    profile_image_url = payload.get("profile_image_url")

    
    if not email or not password or not nickname:
        raise BusinessException(*ErrorCodes.MISSING_REQUIRED_FIELDS)

    
    if not _validate_email(email):
        raise BusinessException(*ErrorCodes.INVALID_EMAIL_FORMAT)

    _validate_nickname(nickname)
    
    _validate_password(password)

   
    if users_model.is_email_exists(email):
        raise BusinessException(*ErrorCodes.EMAIL_ALREADY_EXISTS)
    if users_model.is_nickname_exists(nickname):
        raise BusinessException(*ErrorCodes.NICKNAME_ALREADY_EXISTS)

    users_model.create_user(email, password, nickname, profile_image_url)
    return created(message="signup_success", data=None)


def get_me(user_id: int) -> JSONResponse:
    
    user = users_model.get_user_by_id(user_id)
    if not user:
        raise BusinessException(*ErrorCodes.USER_NOT_FOUND)

   
    data = {
        "id": user["id"],
        "email": user["email"],
        "nickname": user["nickname"],
        "profile_image_url": user.get("profile_image_url")
    }
    return ok(message="read_me_success", data=data)


def update_me(user_id: int, payload: dict) -> JSONResponse:
  
    user = users_model.get_user_by_id(user_id)
    if not user:
        raise BusinessException(*ErrorCodes.USER_NOT_FOUND)

    nickname = (payload.get("nickname") or "").strip()
    profile_image_url = payload.get("profile_image_url")

    
    if nickname:
        _validate_nickname(nickname)
        
      
        if nickname != user["nickname"] and users_model.is_nickname_exists(nickname):
            raise BusinessException(*ErrorCodes.NICKNAME_ALREADY_EXISTS)

    updated = users_model.update_user(
        user_id,
        nickname=nickname or None,
        profile_image_url=profile_image_url
    )
    
    if not updated:
        raise BusinessException(*ErrorCodes.USER_NOT_FOUND)

    data = {
        "id": updated["id"],
        "email": updated["email"],
        "nickname": updated["nickname"],
        "profile_image_url": updated.get("profile_image_url")
    }
    return ok(message="user_updated", data=data)


def update_password(user_id: int, payload: dict) -> JSONResponse:
  
    old_pw = payload.get("old_password") or ""
    new_pw = payload.get("new_password") or ""

    if not old_pw or not new_pw:
        raise BusinessException(*ErrorCodes.MISSING_REQUIRED_FIELDS)

    user = users_model.get_user_by_id(user_id)
    if not user:
        raise BusinessException(*ErrorCodes.USER_NOT_FOUND)

    
    if not verify_password(old_pw, user["password_hash"]):
        raise BusinessException(*ErrorCodes.WRONG_PASSWORD)

   
    _validate_password(new_pw)

    users_model.update_user(user_id, password_hash=hash_password(new_pw))
    return ok(message="password_updated", data=None)


def withdraw(user_id: int) -> JSONResponse:
    
    user = users_model.get_user_by_id(user_id)
    if not user:
        raise BusinessException(*ErrorCodes.USER_NOT_FOUND)

    users_model.delete_user(user_id)
    return ok(message="user_deleted", data=None)