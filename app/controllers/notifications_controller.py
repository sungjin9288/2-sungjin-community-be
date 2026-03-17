from fastapi.responses import JSONResponse

from app.common.exceptions import BusinessException, ErrorCode
from app.common.responses import ok
from app.models import notifications_model


def list_notifications(user_id: int, unread_only: bool = False, limit: int = 50) -> JSONResponse:
    notifications = notifications_model.list_notifications(user_id=user_id, unread_only=unread_only, limit=limit)
    return ok(message="read_notifications_success", data=notifications)


def unread_count(user_id: int) -> JSONResponse:
    return ok(
        message="read_unread_notifications_success",
        data={"unread_count": notifications_model.count_unread_notifications(user_id)},
    )


def mark_read(user_id: int, notification_id: int) -> JSONResponse:
    notification = notifications_model.mark_notification_read(user_id=user_id, notification_id=notification_id)
    if not notification:
        raise BusinessException(ErrorCode.INVALID_REQUEST_FORMAT, "알림을 찾을 수 없습니다.")
    return ok(message="notification_read", data=notification)


def mark_all_read(user_id: int) -> JSONResponse:
    updated_count = notifications_model.mark_all_notifications_read(user_id)
    return ok(message="notifications_read_all", data={"updated_count": updated_count})
