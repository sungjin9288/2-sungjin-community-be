from collections import OrderedDict

from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.db_models import DirectMessage, User
from app.models.base import to_dict as _to_dict
from app.models.social_model import get_hidden_user_ids

SEARCH_LIMIT = 20
MESSAGE_LIMIT = 100


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "nickname": user.nickname,
        "profile_image_url": user.profile_image_url,
    }


def _serialize_message(message: DirectMessage, current_user_id: int) -> dict:
    data = _to_dict(message)
    data["sender"] = _serialize_user(message.sender)
    data["recipient"] = _serialize_user(message.recipient)
    data["is_mine"] = message.sender_id == current_user_id
    return data


def search_users(user_id: int, query: str | None = None) -> list[dict]:
    db = SessionLocal()
    try:
        users_query = db.query(User).filter(User.deleted_at.is_(None), User.id != user_id)
        hidden_user_ids = get_hidden_user_ids(user_id)
        if hidden_user_ids:
            users_query = users_query.filter(User.id.notin_(hidden_user_ids))
        normalized_query = (query or "").strip()
        if normalized_query:
            keyword = f"%{normalized_query}%"
            users_query = users_query.filter(
                or_(User.nickname.ilike(keyword), User.email.ilike(keyword))
            )

        users = users_query.order_by(User.nickname.asc(), User.id.asc()).limit(SEARCH_LIMIT).all()
        return [_serialize_user(user) for user in users]
    finally:
        db.close()


def list_conversations(user_id: int, query: str | None = None) -> list[dict]:
    db = SessionLocal()
    try:
        hidden_user_ids = get_hidden_user_ids(user_id)
        messages = (
            db.query(DirectMessage)
            .options(joinedload(DirectMessage.sender), joinedload(DirectMessage.recipient))
            .filter(
                DirectMessage.deleted_at.is_(None),
                or_(DirectMessage.sender_id == user_id, DirectMessage.recipient_id == user_id),
            )
            .order_by(DirectMessage.created_at.desc(), DirectMessage.id.desc())
            .all()
        )

        conversation_map: OrderedDict[int, dict] = OrderedDict()
        unread_counts: dict[int, int] = {}
        normalized_query = (query or "").strip().lower()

        for message in messages:
            partner = message.recipient if message.sender_id == user_id else message.sender
            if not partner or partner.deleted_at is not None or partner.id in hidden_user_ids:
                continue

            partner_id = partner.id
            unread_counts.setdefault(partner_id, 0)
            if message.recipient_id == user_id and not message.is_read:
                unread_counts[partner_id] += 1

            if partner_id in conversation_map:
                continue

            if normalized_query and normalized_query not in partner.nickname.lower() and normalized_query not in partner.email.lower() and normalized_query not in (message.content or "").lower():
                continue

            conversation_map[partner_id] = {
                "partner": _serialize_user(partner),
                "last_message": {
                    "id": message.id,
                    "content": message.content,
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                    "sender_id": message.sender_id,
                    "recipient_id": message.recipient_id,
                    "is_mine": message.sender_id == user_id,
                },
                "unread_count": 0,
            }

        results = []
        for partner_id, item in conversation_map.items():
            item["unread_count"] = unread_counts.get(partner_id, 0)
            results.append(item)

        return results
    finally:
        db.close()


def list_messages(user_id: int, other_user_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        messages = (
            db.query(DirectMessage)
            .options(joinedload(DirectMessage.sender), joinedload(DirectMessage.recipient))
            .filter(
                DirectMessage.deleted_at.is_(None),
                or_(
                    and_(DirectMessage.sender_id == user_id, DirectMessage.recipient_id == other_user_id),
                    and_(DirectMessage.sender_id == other_user_id, DirectMessage.recipient_id == user_id),
                ),
            )
            .order_by(DirectMessage.created_at.asc(), DirectMessage.id.asc())
            .limit(MESSAGE_LIMIT)
            .all()
        )

        unread_messages = [
            message
            for message in messages
            if message.sender_id == other_user_id and message.recipient_id == user_id and not message.is_read
        ]
        for message in unread_messages:
            message.is_read = True

        if unread_messages:
            db.commit()
            for message in unread_messages:
                db.refresh(message)

        return [_serialize_message(message, user_id) for message in messages]
    finally:
        db.close()


def count_unread_messages(user_id: int) -> int:
    db = SessionLocal()
    try:
        hidden_user_ids = get_hidden_user_ids(user_id)
        query = db.query(DirectMessage).filter(
            DirectMessage.recipient_id == user_id,
            DirectMessage.deleted_at.is_(None),
            DirectMessage.is_read.is_(False),
        )
        if hidden_user_ids:
            query = query.filter(DirectMessage.sender_id.notin_(hidden_user_ids))
        return query.count()
    finally:
        db.close()


def create_message(sender_id: int, recipient_id: int, content: str) -> dict:
    db = SessionLocal()
    try:
        message = DirectMessage(
            sender_id=sender_id,
            recipient_id=recipient_id,
            content=content,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        _ = message.sender
        _ = message.recipient
        return _serialize_message(message, sender_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
