import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.db_models import Comment, Like, Post, PostTag, Session, Tag, User
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    # Keep test isolation simple and explicit.
    db = SessionLocal()
    try:
        for table_model in [Session, Like, Comment, PostTag, Post, Tag, User]:
            db.query(table_model).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture
def unique_email():
    def _make(prefix: str = "user") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:10]}@example.com"

    return _make


@pytest.fixture
def unique_nickname():
    def _make(prefix: str = "u") -> str:
        return f"{prefix}{uuid.uuid4().hex[:6]}"

    return _make
