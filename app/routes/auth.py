from fastapi import APIRouter, Request, Response
from app.controllers import auth_controller
from app.common.auth import SESSION_COOKIE_NAME, get_session_id_from_request

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
def login(payload: dict, response: Response):
    res, session_id = auth_controller.login(payload)
    if session_id:
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
        )
    return res

@router.post("/logout")
def logout(request: Request, response: Response):
    session_id = get_session_id_from_request(request)
    res = auth_controller.logout(session_id)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return res