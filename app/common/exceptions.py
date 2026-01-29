from enum import Enum
from fastapi import HTTPException

class ErrorCode(Enum):
    # 400 Bad Request
    MISSING_REQUIRED_FIELDS = ("missing_required_fields", "필수 값이 없습니다", 400)
    INVALID_REQUEST_FORMAT = ("invalid_request_format", "요청 형식이 올바르지 않습니다", 400)
    INVALID_PAGING_PARAMS = ("invalid_paging_params", "페이징 파라미터가 올바르지 않습니다", 400)
    INVALID_EMAIL_FORMAT = ("invalid_email_format", "이메일 형식이 올바르지 않습니다", 400)
    INVALID_POST_ID = ("invalid_post_id", "게시글 ID가 올바르지 않습니다", 400)
    INVALID_COMMENT_ID = ("invalid_comment_id", "댓글 ID가 올바르지 않습니다", 400)
    
    # 401 Unauthorized
    UNAUTHORIZED = ("unauthorized", "인증이 필요합니다", 401)
    INVALID_CREDENTIALS = ("invalid_credentials", "아이디 또는 비밀번호가 올바르지 않습니다", 401)
    
    # 403 Forbidden
    FORBIDDEN = ("forbidden", "권한이 없습니다", 403)
    
    # 404 Not Found
    EMAIL_NOT_FOUND = ("email_not_found", "이메일을 찾을 수 없습니다", 404)
    USER_NOT_FOUND = ("user_not_found", "사용자를 찾을 수 없습니다", 404)
    POST_NOT_FOUND = ("post_not_found", "게시글을 찾을 수 없습니다", 404)
    COMMENT_NOT_FOUND = ("comment_not_found", "댓글을 찾을 수 없습니다", 404)
    
    # 409 Conflict
    EMAIL_ALREADY_EXISTS = ("email_already_exists", "이미 존재하는 이메일입니다", 409)
    NICKNAME_ALREADY_EXISTS = ("nickname_already_exists", "이미 존재하는 닉네임입니다", 409)
    
    # 422 Unprocessable Entity
    INVALID_PASSWORD = ("invalid_password", "비밀번호는 8-20자, 대소문자, 숫자, 특수문자를 각각 1개 이상 포함해야 합니다", 422)
    PASSWORD_TOO_SHORT = ("password_too_short", "비밀번호는 최소 8자 이상이어야 합니다", 422)
    PASSWORD_TOO_LONG = ("password_too_long", "비밀번호는 최대 20자 이하여야 합니다", 422)
    
    # 500 Internal Server Error
    INTERNAL_SERVER_ERROR = ("internal_server_error", "서버 오류가 발생했습니다", 500)
    DATABASE_ERROR = ("database_error", "데이터베이스 오류가 발생했습니다", 500)
    
    @property
    def code(self) -> str:
        return self.value[0]
    
    @property
    def message(self) -> str:
        return self.value[1]
    
    @property
    def status_code(self) -> int:
        return self.value[2]


# ==================== 커스텀 예외 클래스 (수정됨) ====================

# ★ 중요 수정: 이름을 BusinessException으로 변경하고 HTTPException을 상속받음
class BusinessException(HTTPException):
    def __init__(self, error_code: ErrorCode, custom_message: str = None):
        super().__init__(
            status_code=error_code.status_code,
            detail=custom_message or error_code.message
        )
        self.error_code = error_code.code


# 아래 클래스들은 BusinessException을 상속받도록 연결해두었습니다.
# 필요할 때 편하게 골라 쓸 수 있습니다.

class MissingRequiredFieldsError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.MISSING_REQUIRED_FIELDS, custom_message)

class InvalidRequestFormatError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.INVALID_REQUEST_FORMAT, custom_message)

class InvalidPagingParamsError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.INVALID_PAGING_PARAMS, custom_message)

class InvalidEmailFormatError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.INVALID_EMAIL_FORMAT, custom_message)

class UnauthorizedError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.UNAUTHORIZED, custom_message)

class InvalidCredentialsError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.INVALID_CREDENTIALS, custom_message)

class ForbiddenError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.FORBIDDEN, custom_message)

class EmailNotFoundError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.EMAIL_NOT_FOUND, custom_message)

class UserNotFoundError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.USER_NOT_FOUND, custom_message)

class PostNotFoundError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.POST_NOT_FOUND, custom_message)

class CommentNotFoundError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.COMMENT_NOT_FOUND, custom_message)

class EmailAlreadyExistsError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.EMAIL_ALREADY_EXISTS, custom_message)

class NicknameAlreadyExistsError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.NICKNAME_ALREADY_EXISTS, custom_message)

class InvalidPasswordError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.INVALID_PASSWORD, custom_message)

class InternalServerError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.INTERNAL_SERVER_ERROR, custom_message)

class DatabaseError(BusinessException):
    def __init__(self, custom_message: str = None):
        super().__init__(ErrorCode.DATABASE_ERROR, custom_message)