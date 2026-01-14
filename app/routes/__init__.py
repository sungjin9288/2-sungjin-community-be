from fastapi import APIRouter

from app.routes.users import router as users_router
from app.routes.posts import router as posts_router
from app.routes.comments import router as comments_router

router = APIRouter()
router.include_router(users_router, prefix="/users", tags=["Users"])
router.include_router(posts_router, prefix="/posts", tags=["Posts"])
router.include_router(comments_router, tags=["Comments"])
