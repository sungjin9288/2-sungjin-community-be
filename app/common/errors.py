from dataclasses import dataclass


@dataclass(frozen=True)
class AppError:
    code: str
    message: str


# ----- Common -----
INVALID_REQUEST = AppError(code="INVALID_REQUEST", message="invalid_request")
INTERNAL_SERVER_ERROR = AppError(code="INTERNAL_SERVER_ERROR", message="internal_server_error")

# ----- Auth / Users -----
MISSING_REQUIRED_FIELDS = AppError(code="MISSING_REQUIRED_FIELDS", message="missing_required_fields")
EMAIL_ALREADY_EXISTS = AppError(code="EMAIL_ALREADY_EXISTS", message="email_already_exists")
NICKNAME_ALREADY_EXISTS = AppError(code="NICKNAME_ALREADY_EXISTS", message="nickname_already_exists")
EMAIL_NOT_FOUND = AppError(code="EMAIL_NOT_FOUND", message="email_not_found")
WRONG_PASSWORD = AppError(code="WRONG_PASSWORD", message="wrong_password")
UNAUTHORIZED = AppError(code="UNAUTHORIZED", message="unauthorized")
INVALID_TOKEN = AppError(code="INVALID_TOKEN", message="invalid_token")

# ----- Posts -----
POST_NOT_FOUND = AppError(code="POST_NOT_FOUND", message="post_not_found")
PAGE_INVALID = AppError(code="PAGE_INVALID", message="page_invalid")
LIMIT_INVALID = AppError(code="LIMIT_INVALID", message="limit_invalid")
TITLE_REQUIRED = AppError(code="TITLE_REQUIRED", message="title_required")
CONTENT_REQUIRED = AppError(code="CONTENT_REQUIRED", message="content_required")

# ----- Comments -----
COMMENT_NOT_FOUND = AppError(code="COMMENT_NOT_FOUND", message="comment_not_found")
