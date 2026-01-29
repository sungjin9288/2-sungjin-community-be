from fastapi.responses import JSONResponse
from app.common.responses import ok, created
# ★ 수정: 새로운 예외 클래스 Import
from app.common.exceptions import (
    BusinessException, ErrorCode,
    MissingRequiredFieldsError, PostNotFoundError,
    CommentNotFoundError, ForbiddenError,
    InvalidRequestFormatError
)
from app.models import posts_model, comments_model


def _validate_comment(content: str) -> None:
    # 기획서에는 명시적 길이 제한이 없으나(TEXT 저장), 
    # 데이터베이스 보호를 위해 500자 또는 1000자 정도의 안전장치는 두는 것이 좋습니다.
    # 기존 코드의 500자 제한을 유지하되 에러 형식을 변경했습니다.
    if len(content) > 500:
        raise BusinessException(
            ErrorCode.INVALID_REQUEST_FORMAT,
            "댓글은 최대 500자까지 가능합니다."
        )


def list_comments(post_id: int, user_id: int | None = None) -> JSONResponse:
    # 게시글이 존재하는지 먼저 확인
    if not posts_model.find_post(post_id):
        raise PostNotFoundError()
    
    comments = comments_model.list_comments(post_id, user_id)
    return ok(message="read_comments_success", data=comments)


def create_comment(user_id: int, post_id: int, payload: dict) -> JSONResponse:
    content = (payload.get("content") or "").strip()
    
    # 기획서: "댓글 텍스트 모두 삭제시 버튼 비활성화" -> 백엔드에서도 빈 값 차단
    if not content:
        raise MissingRequiredFieldsError("댓글 내용을 입력해주세요.")

    _validate_comment(content)

    if not posts_model.find_post(post_id):
        raise PostNotFoundError()

    comment = comments_model.create_comment(user_id, post_id, content)
    return created(message="comment_created", data=comment)


# ★ 추가됨: 기획서 5번 "댓글 수정" 기능을 위해 추가
def update_comment(user_id: int, post_id: int, comment_id: int, payload: dict) -> JSONResponse:
    comment = comments_model.find_comment(comment_id)
    if not comment:
        raise CommentNotFoundError()

    # URL의 post_id와 실제 댓글의 post_id 일치 여부 확인
    if comment["post_id"] != post_id:
        raise CommentNotFoundError()

    # 권한 체크
    if comment["user_id"] != user_id:
        raise ForbiddenError("댓글 수정 권한이 없습니다.")

    content = (payload.get("content") or "").strip()
    
    if not content:
        raise MissingRequiredFieldsError("댓글 내용을 입력해주세요.")
        
    _validate_comment(content)

    # 모델에 update_comment 함수가 필요합니다. 
    updated = comments_model.update_comment(comment_id, content)
    if not updated:
        raise CommentNotFoundError()

    return ok(message="comment_updated", data=updated)


def delete_comment(user_id: int, post_id: int, comment_id: int) -> JSONResponse:
    comment = comments_model.find_comment(comment_id)
    if not comment:
        raise CommentNotFoundError()

    # URL의 post_id와 실제 댓글의 post_id 일치 여부 확인
    if comment["post_id"] != post_id:
        raise CommentNotFoundError()

    # 권한 체크
    if comment["user_id"] != user_id:
        raise ForbiddenError("댓글 삭제 권한이 없습니다.")

    comments_model.delete_comment(comment_id)
    return ok(message="comment_deleted", data=None)