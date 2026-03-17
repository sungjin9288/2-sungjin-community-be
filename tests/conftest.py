import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB_PATH = Path('/tmp/community-be-test.db')
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB_PATH}'

if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

from app.database import SessionLocal, engine
from app.db_models import (
    Base,
    Comment,
    DirectMessage,
    Like,
    Notification,
    Post,
    PostBookmark,
    PostTag,
    Report,
    Session,
    Tag,
    User,
    UserBlock,
)
from app.main import app, ensure_additive_schema

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
ensure_additive_schema()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    db = SessionLocal()
    try:
        for table_model in [
            Notification,
            Report,
            UserBlock,
            PostBookmark,
            DirectMessage,
            Session,
            Like,
            Comment,
            PostTag,
            Post,
            Tag,
            User,
        ]:
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
