
from typing import Optional
from fastapi import Request
from app.models import users_model

SESSION_COOKIE_NAME = "session_id"


def get_session_id_from_request(request: Request) -> Optional[str]:

    sid = request.cookies.get(SESSION_COOKIE_NAME)
    return sid or None


def get_user_id_from_request(request: Request) -> Optional[int]:

    sid = get_session_id_from_request(request)
    if not sid:
        return None
    return users_model.get_user_id_by_session(sid)