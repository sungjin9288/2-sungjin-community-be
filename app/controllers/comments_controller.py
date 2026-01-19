from fastapi.responses import JSONResponse
from app.common.responses import ok, created
from app.common.exceptions import BusinessException, ErrorCodes
from app.models import posts_model, comments_model

def list_comments(post_id: int) -> JSONResponse:
    if not posts_model.find_post(post_id):
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)
    return ok("댓글 목록 조회 성공", comments_model.list_comments(post_id))

def create_comment(user_id: int, post_id: int, payload: dict) -> JSONResponse:
    content = (payload.get("content") or "").strip()
    if not content:
        raise BusinessException(*ErrorCodes.MISSING_REQUIRED_FIELDS)

    if not posts_model.find_post(post_id):
        raise BusinessException(*ErrorCodes.POST_NOT_FOUND)

    c = comments_model.create_comment(user_id, post_id, content)
    return created("댓글이 작성되었습니다.", c)

def delete_comment(user_id: int, post_id: int, comment_id: int) -> JSONResponse:
    comment = comments_model.find_comment(comment_id)
    if not comment:
        raise BusinessException(*ErrorCodes.COMMENT_NOT_FOUND)
        
    if comment["user_id"] != user_id:
        raise BusinessException(*ErrorCodes.FORBIDDEN)
        
    comments_model.delete_comment(comment_id)
    return ok("댓글이 삭제되었습니다.")