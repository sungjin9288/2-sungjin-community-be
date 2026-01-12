from fastapi.responses import JSONResponse
from app.common.responses import ok, created, bad_request, unauthorized, conflict, server_error

# stub DB
USERS = [
    {"email": "start@community.com", "password": "start21", "nickname": "starter"}
]

def signup(payload: dict) -> JSONResponse:
    try:
        email = payload.get("email")
        password = payload.get("password")
        nickname = payload.get("nickname")

        if not email or not password or not nickname:
            return bad_request("missing_required_fields")

        if any(u["email"] == email for u in USERS):
            return conflict("email_already_exists")

        if any(u["nickname"] == nickname for u in USERS):
            return conflict("nickname_already_exists")

        USERS.append({"email": email, "password": password, "nickname": nickname})
        return created("signup_success", None)
    except Exception:
        return server_error()


def login(payload: dict) -> JSONResponse:
    try:
        email = payload.get("email")
        password = payload.get("password")

        if not email or not password:
            return bad_request("missing_required_fields")

        user = next((u for u in USERS if u["email"] == email), None)
        if user is None:
            return unauthorized("email_not_found")
        if user["password"] != password:
            return unauthorized("wrong_password")

        posts_preview = [
            {"post_id": 1, "title": "welcome", "author": user["nickname"]},
            {"post_id": 2, "title": "rules", "author": "admin"},
        ]
        data = {"access_token": "token-1", "token_type": "bearer", "posts": posts_preview}
        return ok("login_success", data)
    except Exception:
        return server_error()


def logout(authorization: str | None) -> JSONResponse:
    try:
        if not authorization or not authorization.startswith("Bearer "):
            return unauthorized("unauthorized")

        token = authorization.split(" ", 1)[1].strip()
        if token != "token-1":
            return unauthorized("invalid_token")

        return ok("logout_success", None)
    except Exception:
        return server_error()
