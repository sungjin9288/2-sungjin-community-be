from fastapi.responses import JSONResponse

from app.common.exceptions import (
    BusinessException,
    ErrorCode,
    MissingRequiredFieldsError,
    UserNotFoundError,
)
from app.common.responses import created, ok
from app.models import messages_model, notifications_model, social_model, users_model

MAX_MESSAGE_LENGTH = 1000


def _validate_recipient(user_id: int, recipient_id: int) -> None:
    if recipient_id <= 0:
        raise UserNotFoundError()
    if recipient_id == user_id:
        raise BusinessException(
            ErrorCode.INVALID_REQUEST_FORMAT,
            "자기 자신에게는 메시지를 보낼 수 없습니다.",
        )
    if not users_model.get_user_by_id(recipient_id):
        raise UserNotFoundError()
    if social_model.is_blocked_between(user_id, recipient_id):
        raise BusinessException(ErrorCode.FORBIDDEN, "차단 관계의 사용자와는 메시지를 주고받을 수 없습니다.")


def _validate_content(content: str) -> str:
    normalized = (content or "").strip()
    if not normalized:
        raise MissingRequiredFieldsError("메시지 내용을 입력해주세요.")
    if len(normalized) > MAX_MESSAGE_LENGTH:
        raise BusinessException(
            ErrorCode.INVALID_REQUEST_FORMAT,
            f"메시지는 최대 {MAX_MESSAGE_LENGTH}자까지 작성 가능합니다.",
        )
    return normalized


def search_users(user_id: int, query: str | None = None) -> JSONResponse:
    users = messages_model.search_users(user_id=user_id, query=query)
    return ok(message="search_message_users_success", data=users)


def list_conversations(user_id: int, query: str | None = None) -> JSONResponse:
    conversations = messages_model.list_conversations(user_id=user_id, query=query)
    return ok(message="read_conversations_success", data=conversations)


def list_messages(user_id: int, other_user_id: int) -> JSONResponse:
    _validate_recipient(user_id, other_user_id)
    messages = messages_model.list_messages(user_id=user_id, other_user_id=other_user_id)
    return ok(message="read_messages_success", data=messages)


def unread_count(user_id: int) -> JSONResponse:
    return ok(message="read_unread_messages_success", data={"unread_count": messages_model.count_unread_messages(user_id)})


def send_message(user_id: int, recipient_id: int, content: str) -> JSONResponse:
    _validate_recipient(user_id, recipient_id)
    normalized_content = _validate_content(content)
    message = messages_model.create_message(
        sender_id=user_id,
        recipient_id=recipient_id,
        content=normalized_content,
    )
    notifications_model.create_notification(
        recipient_id,
        actor_id=user_id,
        notification_type="direct_message",
        title="새로운 1:1 메시지가 도착했습니다.",
        body=normalized_content[:120],
        link_url=f"/messages?userId={user_id}",
        entity_type="user",
        entity_id=user_id,
    )
    return created(message="message_sent", data=message)
