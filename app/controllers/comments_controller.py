
from fastapi.responses import JSONResponse
from app.common.responses import ok, created
from app.common.exceptions import BusinessException, ErrorCodes
from app.models import posts_model, comments_model


def _validate_comment(content: str) -> None:
    
    if len(content) > 500:
        raise BusinessException(
            "invalid_comment_policy",
            "댓글은 최대 500자까지 가능합니다.",
            422,
            data={"max_length": 500}
        )


def list_comments(post_id: int) -> JSONResponse:

    if not posts_model.find_post(post_id):
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)
    
    comments = comments_model.list_comments(post_id)
    return ok(message="read_comments_success", data=comments)


def create_comment(user_id: int, post_id: int, payload: dict) -> JSONResponse:

    content = (payload.get("content") or "").strip()
    
    if not content:
        raise BusinessException(*ErrorCodes.MISSING_REQUIRED_FIELDS)


    _validate_comment(content)


    if not posts_model.find_post(post_id):
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)

    comment = comments_model.create_comment(user_id, post_id, content)
    return created(message="comment_created", data=comment)


def delete_comment(user_id: int, post_id: int, comment_id: int) -> JSONResponse:

    comment = comments_model.find_comment(comment_id)
    if not comment:
        raise BusinessException(*ErrorCodes.COMMENT_NOT_FOUND)

    # URL의 post_id와 실제 댓글의 post_id 일치 여부 확인
    if comment["post_id"] != post_id:
        raise BusinessException(*ErrorCodes.COMMENT_NOT_FOUND)

    # 권한 체크
    if comment["user_id"] != user_id:
        raise BusinessException(*ErrorCodes.PERMISSION_DENIED)

    comments_model.delete_comment(comment_id)
    return ok(message="comment_deleted", data=None)