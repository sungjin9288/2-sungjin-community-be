from fastapi.responses import JSONResponse

from app.common.responses import ok, created, bad_request, unauthorized, conflict, server_error
from app.common.errors import (
    MISSING_REQUIRED_FIELDS,
    EMAIL_ALREADY_EXISTS,
    NICKNAME_ALREADY_EXISTS,
    EMAIL_NOT_FOUND,
    WRONG_PASSWORD,
    UNAUTHORIZED,
    INVALID_TOKEN,
    INTERNAL_SERVER_ERROR,
)
from app.common.auth import parse_bearer_token
from app.models import users_model
from app.models import posts_model


def signup(payload: dict) -> JSONResponse:
    try:
        email = payload.get("email")
        password = payload.get("password")
        nickname = payload.get("nickname")

        if not email or not password or not nickname:
            return bad_request(MISSING_REQUIRED_FIELDS.message)

        if users_model.is_email_exists(email):
            return conflict(EMAIL_ALREADY_EXISTS.message)

        if users_model.is_nickname_exists(nickname):
            return conflict(NICKNAME_ALREADY_EXISTS.message)

        users_model.create_user(email=email, password=password, nickname=nickname)
        return created("signup_success", None)

    except Exception:
        return server_error(INTERNAL_SERVER_ERROR.message)


def login(payload: dict) -> JSONResponse:
    try:
        email = payload.get("email")
        password = payload.get("password")

        if not email or not password:
            return bad_request(MISSING_REQUIRED_FIELDS.message)

        user = users_model.find_user_by_email(email)
        if user is None:
            return unauthorized(EMAIL_NOT_FOUND.message)

        if user["password"] != password:
            return unauthorized(WRONG_PASSWORD.message)

        token = users_model.create_session(user_id=user["id"])

        posts = posts_model.list_posts(page=1, limit=10)

        data = {
            "access_token": token,
            "token_type": "bearer",
            "posts": posts,  # {"page","limit","total","items"}
        }
        return ok("login_success", data)

    except Exception:
        return server_error(INTERNAL_SERVER_ERROR.message)


def logout(authorization: str | None) -> JSONResponse:
    try:
        token = parse_bearer_token(authorization)
        if not token:
            return unauthorized(UNAUTHORIZED.message)

        user_id = users_model.get_user_id_by_token(token)
        if user_id is None:
            return unauthorized(INVALID_TOKEN.message)

        users_model.delete_session(token)
        return ok("logout_success", None)

    except Exception:
        return server_error(INTERNAL_SERVER_ERROR.message)
