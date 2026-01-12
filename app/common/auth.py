from typing import Optional

VALID_TOKEN = "token-1"


def is_authorized(authorization: Optional[str]) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        return False
    token = authorization.split(" ", 1)[1].strip()
    return token == VALID_TOKEN
