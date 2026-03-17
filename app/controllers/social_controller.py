from fastapi.responses import JSONResponse

from app.common.exceptions import BusinessException, ErrorCode, UserNotFoundError
from app.common.responses import created, ok
from app.models import social_model, users_model

ALLOWED_REPORT_REASONS = {
    "spam",
    "abuse",
    "harassment",
    "nudity",
    "violence",
    "copyright",
    "etc",
}


def list_blocks(user_id: int) -> JSONResponse:
    return ok(message="read_blocks_success", data=social_model.list_blocked_users(user_id))


def create_block(user_id: int, blocked_user_id: int) -> JSONResponse:
    if blocked_user_id == user_id:
        raise BusinessException(ErrorCode.INVALID_REQUEST_FORMAT, "자기 자신은 차단할 수 없습니다.")
    if not users_model.get_user_by_id(blocked_user_id):
        raise UserNotFoundError()
    created_block = social_model.create_block(user_id, blocked_user_id)
    if not created_block:
        raise BusinessException(ErrorCode.INVALID_REQUEST_FORMAT, "이미 차단한 사용자입니다.")
    return created(message="user_blocked", data=created_block)


def delete_block(user_id: int, blocked_user_id: int) -> JSONResponse:
    social_model.delete_block(user_id, blocked_user_id)
    return ok(message="user_unblocked", data={"blocked_user_id": blocked_user_id})


def create_report(user_id: int, target_type: str, target_id: int, reason: str, description: str | None) -> JSONResponse:
    normalized_reason = (reason or "").strip().lower()
    if normalized_reason not in ALLOWED_REPORT_REASONS:
        raise BusinessException(ErrorCode.INVALID_REQUEST_FORMAT, "지원하지 않는 신고 사유입니다.")
    report = social_model.create_report(
        reporter_id=user_id,
        target_type=target_type,
        target_id=target_id,
        reason=normalized_reason,
        description=(description or "").strip() or None,
    )
    if not report:
        raise BusinessException(ErrorCode.INVALID_REQUEST_FORMAT, "신고 대상을 찾을 수 없습니다.")
    return created(message="report_created", data=report)
