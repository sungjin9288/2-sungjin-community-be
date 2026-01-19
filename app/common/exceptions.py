


class BusinessException(Exception):
 
    def __init__(self, code: str, message: str, status_code: int = 400, data: dict = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data
        super().__init__(message)


class ErrorCodes:

    
    # 400 Bad Request
    MISSING_REQUIRED_FIELDS = ("missing_required_fields", "필수 입력값이 누락되었습니다.", 400)
    INVALID_REQUEST_BODY = ("invalid_request_body", "요청 형식이 올바르지 않습니다.", 400)
    INVALID_PAGING_PARAMS = ("invalid_paging_params", "페이징 파라미터가 올바르지 않습니다.", 400)
    INVALID_EMAIL_FORMAT = ("invalid_email_format", "이메일 형식이 올바르지 않습니다.", 400)
    INVALID_POST_ID = ("invalid_post_id", "게시글 ID가 올바르지 않습니다.", 400)
    INVALID_COMMENT_ID = ("invalid_comment_id", "댓글 ID가 올바르지 않습니다.", 400)

    # 401 Unauthorized
    UNAUTHORIZED = ("unauthorized", "인증이 필요합니다.", 401)
    INVALID_CREDENTIALS = ("invalid_credentials", "이메일 또는 비밀번호가 올바르지 않습니다.", 401)
    EMAIL_NOT_FOUND = ("email_not_found", "등록되지 않은 이메일입니다.", 401)
    WRONG_PASSWORD = ("wrong_password", "비밀번호가 일치하지 않습니다.", 401)
    INVALID_TOKEN = ("invalid_token", "유효하지 않은 토큰입니다.", 401)
    EXPIRED_TOKEN = ("expired_token", "만료된 토큰입니다.", 401)

    # 403 Forbidden
    PERMISSION_DENIED = ("permission_denied", "권한이 없습니다.", 403)

    # 404 Not Found
    USER_NOT_FOUND = ("user_not_found", "사용자를 찾을 수 없습니다.", 404)
    POST_NOT_FOUND = ("post_not_found", "게시글을 찾을 수 없습니다.", 404)
    COMMENT_NOT_FOUND = ("comment_not_found", "댓글을 찾을 수 없습니다.", 404)
    LIKE_NOT_FOUND = ("like_not_found", "좋아요를 찾을 수 없습니다.", 404)

    # 409 Conflict
    EMAIL_ALREADY_EXISTS = ("email_already_exists", "이미 사용 중인 이메일입니다.", 409)
    NICKNAME_ALREADY_EXISTS = ("nickname_already_exists", "이미 사용 중인 닉네임입니다.", 409)
    LIKE_ALREADY_EXISTS = ("like_already_exists", "이미 좋아요를 눌렀습니다.", 409)

    # 422 Unprocessable Entity
    INVALID_PASSWORD_POLICY = ("invalid_password_policy", "비밀번호 정책을 만족하지 않습니다.", 422)
    INVALID_NICKNAME_POLICY = ("invalid_nickname_policy", "닉네임 정책을 만족하지 않습니다.", 422)
    INVALID_TITLE_POLICY = ("invalid_title_policy", "제목 길이가 제한을 초과했습니다.", 422)
    INVALID_CONTENT_POLICY = ("invalid_content_policy", "내용 길이가 제한을 초과했습니다.", 422)
    INVALID_COMMENT_POLICY = ("invalid_comment_policy", "댓글 길이가 제한을 초과했습니다.", 422)

    # 429 Too Many Requests
    TOO_MANY_REQUESTS = ("too_many_requests", "너무 많은 요청이 발생했습니다.", 429)

    # 500 Internal Server Error
    INTERNAL_SERVER_ERROR = ("internal_server_error", "서버 내부 오류가 발생했습니다.", 500)