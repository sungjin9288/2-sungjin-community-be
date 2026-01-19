class BusinessException(Exception):
    """비즈니스 로직 처리 중 발생하는 예외"""
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

class ErrorCodes:
    # 400 Bad Request
    MISSING_REQUIRED_FIELDS = ("MISSING_REQUIRED_FIELDS", "필수 입력값이 누락되었습니다.", 400)
    INVALID_REQUEST = ("INVALID_REQUEST", "요청 형식이 올바르지 않습니다.", 400)

    # 401 Unauthorized
    UNAUTHORIZED = ("UNAUTHORIZED", "인증이 필요합니다.", 401)
    INVALID_CREDENTIALS = ("INVALID_CREDENTIALS", "이메일 또는 비밀번호가 올바르지 않습니다.", 401)

    # 403 Forbidden
    FORBIDDEN = ("FORBIDDEN", "권한이 없습니다.", 403)

    # 404 Not Found
    USER_NOT_FOUND = ("USER_NOT_FOUND", "사용자를 찾을 수 없습니다.", 404)
    POST_NOT_FOUND = ("POST_NOT_FOUND", "게시글을 찾을 수 없습니다.", 404)
    COMMENT_NOT_FOUND = ("COMMENT_NOT_FOUND", "댓글을 찾을 수 없습니다.", 404)

    # 409 Conflict
    EMAIL_ALREADY_EXISTS = ("EMAIL_ALREADY_EXISTS", "이미 사용 중인 이메일입니다.", 409)
    NICKNAME_ALREADY_EXISTS = ("NICKNAME_ALREADY_EXISTS", "이미 사용 중인 닉네임입니다.", 409)

    # 500 Internal Server Error
    INTERNAL_SERVER_ERROR = ("INTERNAL_SERVER_ERROR", "서버 내부 오류가 발생했습니다.", 500)