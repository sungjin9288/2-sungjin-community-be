import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import db_models
from app.common.exceptions import BusinessException
from app.common.responses import fail
from app.core.logger import setup_logging
from app.database import engine
from app.routes import auth, comments, images, messages, notifications, posts, social, users


def ensure_runtime_directories() -> None:
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    (uploads_dir / "profile").mkdir(exist_ok=True)
    (uploads_dir / "post").mkdir(exist_ok=True)

    static_dir = Path("static")
    static_dir.mkdir(exist_ok=True)


def ensure_additive_schema() -> None:
    inspector = inspect(engine)
    try:
        comment_columns = {column["name"] for column in inspector.get_columns("comments")}
    except Exception:
        comment_columns = set()

    if comment_columns and "parent_comment_id" not in comment_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE comments ADD COLUMN parent_comment_id INTEGER"))


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
    ensure_runtime_directories()
    db_models.Base.metadata.create_all(bind=engine)
    ensure_additive_schema()
    yield
    logger.info("Application shutting down...")


app = FastAPI(title="Community API", version="1.3.0", lifespan=lifespan)


default_origins = "http://localhost:3001,http://127.0.0.1:3001"
allow_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", default_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_runtime_directories()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(comments.router)
app.include_router(images.router)
app.include_router(messages.router)
app.include_router(notifications.router)
app.include_router(social.router)


@app.get("/")
async def root():
    return {"message": "Community API Server"}


@app.get("/health")
async def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "db": "ok"}
    except Exception as exc:
        logger.error("Health check DB connection failed: %s", exc)
        return JSONResponse(
            content={"status": "unhealthy", "db": "error"},
            status_code=503,
        )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("Request: %s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info("Response: %s", response.status_code)
    return response


@app.exception_handler(BusinessException)
async def handle_business_exception(_: Request, exc: BusinessException):
    return fail(
        status_code=exc.status_code,
        message=getattr(exc, "error_code", "business_error"),
        data={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError):
    return fail(
        status_code=400,
        message="invalid_request_format",
        data={"errors": exc.errors()},
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(_: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "http_error"
    return fail(status_code=exc.status_code, message=message, data=None)


@app.exception_handler(Exception)
async def handle_unexpected_exception(_: Request, exc: Exception):
    logger.exception("Unhandled server error: %s", exc)
    return fail(status_code=500, message="internal_server_error", data=None)
