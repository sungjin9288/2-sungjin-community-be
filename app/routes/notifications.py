from fastapi import APIRouter, Depends, Query

from app.common.deps import get_current_user_id
from app.controllers import notifications_controller

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
):
    return notifications_controller.list_notifications(user_id=user_id, unread_only=unread_only, limit=limit)


@router.get("/unread-count")
def unread_count(user_id: int = Depends(get_current_user_id)):
    return notifications_controller.unread_count(user_id=user_id)


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, user_id: int = Depends(get_current_user_id)):
    return notifications_controller.mark_read(user_id=user_id, notification_id=notification_id)


@router.post("/read-all")
def mark_all_read(user_id: int = Depends(get_current_user_id)):
    return notifications_controller.mark_all_read(user_id=user_id)
