from fastapi.responses import JSONResponse
from app.common.responses import created, ok
from app.common.exceptions import BusinessException, ErrorCodes
from app.common.security import hash_password, verify_password
from app.models import users_model

def signup(payload: dict) -> JSONResponse:
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""
    nickname = (payload.get("nickname") or "").strip()
    profile_image_url = payload.get("profile_image_url")

    if not email or not password or not nickname:
        raise BusinessException(*ErrorCodes.MISSING_REQUIRED_FIELDS)

    if users_model.is_email_exists(email):
        raise BusinessException(*ErrorCodes.EMAIL_ALREADY_EXISTS)
    if users_model.is_nickname_exists(nickname):
        raise BusinessException(*ErrorCodes.NICKNAME_ALREADY_EXISTS)

    users_model.create_user(email, password, nickname, profile_image_url)
    return created("회원가입이 완료되었습니다.")

def get_me(user_id: int) -> JSONResponse:
    user = users_model.get_user_by_id(user_id)
    if not user:
        raise BusinessException(*ErrorCodes.USER_NOT_FOUND)
    
    data = user.copy()
    data.pop("password_hash", None)
    return ok("내 정보 조회 성공", data)

def update_me(user_id: int, payload: dict) -> JSONResponse:
    nickname = (payload.get("nickname") or "").strip()
    profile_image_url = payload.get("profile_image_url")
    
    user = users_model.get_user_by_id(user_id)
    if nickname and nickname != user["nickname"] and users_model.is_nickname_exists(nickname):
        raise BusinessException(*ErrorCodes.NICKNAME_ALREADY_EXISTS)
        
    updated = users_model.update_user(user_id, nickname=nickname, profile_image_url=profile_image_url)
    
    data = updated.copy()
    data.pop("password_hash", None)
    return ok("회원 정보가 수정되었습니다.", data)

def update_password(user_id: int, payload: dict) -> JSONResponse:
    old_pw = payload.get("old_password")
    new_pw = payload.get("new_password")
    
    if not old_pw or not new_pw:
        raise BusinessException(*ErrorCodes.MISSING_REQUIRED_FIELDS)
        
    user = users_model.get_user_by_id(user_id)
    if not verify_password(old_pw, user["password_hash"]):
        raise BusinessException(*ErrorCodes.INVALID_CREDENTIALS)
        
    users_model.update_user(user_id, password_hash=hash_password(new_pw))
    return ok("비밀번호가 변경되었습니다.")

def withdraw(user_id: int) -> JSONResponse:
    users_model.delete_user(user_id)
    return ok("회원 탈퇴가 완료되었습니다.")