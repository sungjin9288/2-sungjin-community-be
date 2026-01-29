from fastapi import Request
from app.common.auth import get_user_id_from_request
from app.common.exceptions import UnauthorizedError


def get_current_user_id(request: Request) -> int:
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise UnauthorizedError()
    return user_id

def get_current_user_id_optional(request: Request) -> int | None:
    return get_user_id_from_request(request)

require_user_id = get_current_user_id