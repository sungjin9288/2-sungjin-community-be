from fastapi.responses import JSONResponse
from app.common.responses import ok
from app.common.exceptions import BusinessException, ErrorCodes
from app.common.security import verify_password
from app.models import users_model

def login(payload: dict) -> tuple[JSONResponse, str]:
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""

    if not email or not password:
        raise BusinessException(*ErrorCodes.MISSING_REQUIRED_FIELDS)

    user = users_model.find_user_by_email(email)
    if not user:
        raise BusinessException(*ErrorCodes.INVALID_CREDENTIALS)

    if not verify_password(password, user.get("password_hash", "")):
        raise BusinessException(*ErrorCodes.INVALID_CREDENTIALS)

    session_id = users_model.create_session(user_id=user["id"])
    return ok("로그인에 성공했습니다."), session_id

def logout(session_id: str | None) -> JSONResponse:
    if not session_id:
        raise BusinessException(*ErrorCodes.UNAUTHORIZED)
    
    users_model.delete_session(session_id)
    return ok("로그아웃 되었습니다.")