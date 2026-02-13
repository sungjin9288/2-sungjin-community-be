from typing import Optional

from fastapi import Request

from app.common.jwt_tokens import decode_access_token


def get_bearer_token_from_request(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization")
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def get_user_id_from_request(request: Request) -> Optional[int]:
    access_token = get_bearer_token_from_request(request)
    if not access_token:
        return None
    return decode_access_token(access_token)
