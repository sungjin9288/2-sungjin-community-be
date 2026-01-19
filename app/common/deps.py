
from fastapi import Request
from app.common.auth import get_user_id_from_request
from app.common.exceptions import BusinessException, ErrorCodes


def require_user_id(request: Request) -> int:

    user_id = get_user_id_from_request(request)
    if not user_id:
        raise BusinessException(*ErrorCodes.UNAUTHORIZED)
    return user_id