from datetime import datetime


def to_dict(obj) -> dict | None:
    """SQLAlchemy ORM 객체를 dict로 변환. datetime은 ISO 8601 문자열로 직렬화."""
    if not obj:
        return None
    return {
        c.name: (
            getattr(obj, c.name).isoformat()
            if isinstance(getattr(obj, c.name), datetime)
            else getattr(obj, c.name)
        )
        for c in obj.__table__.columns
    }
