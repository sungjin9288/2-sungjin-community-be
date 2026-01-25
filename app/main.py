from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
from pathlib import Path

from app.routes import auth, users, posts, comments, images

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Community API", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "http://127.0.0.1:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 업로드 디렉토리 분리
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
(uploads_dir / "profile").mkdir(exist_ok=True)
(uploads_dir / "post").mkdir(exist_ok=True)

# Static 파일 제공 (CSS, JS, 이미지 등)
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 라우터 등록
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(comments.router)
app.include_router(images.router)

@app.get("/")
async def root():
    return {"message": "Community API Server"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response