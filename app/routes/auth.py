
from fastapi import APIRouter, Request, Response
from app.controllers import auth_controller
from app.common.auth import SESSION_COOKIE_NAME, get_session_id_from_request

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(payload: dict, response: Response):

    session_id = auth_controller.login(payload)

    # 세션 쿠키 설정
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,       # XSS 방어
        samesite="lax",      # CSRF 방어
        secure=False,        # 로컬 개발용 (프로덕션에서는 True)
        path="/",
        max_age=86400 * 7    # 7일
    )
    
    return {"message": "login_success", "data": None}


@router.post("/logout")
def logout(request: Request, response: Response):

    session_id = get_session_id_from_request(request)
    
    if session_id:
        auth_controller.logout(session_id)

   
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    
    return {"message": "logout_success", "data": None}