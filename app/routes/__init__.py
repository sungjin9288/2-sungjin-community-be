
from fastapi import APIRouter
from app.routes.users import router as users_router
from app.routes.auth import router as auth_router
from app.routes.posts import router as posts_router
from app.routes.comments import router as comments_router

router = APIRouter()

router.include_router(users_router)
router.include_router(auth_router)
router.include_router(posts_router)
router.include_router(comments_router)