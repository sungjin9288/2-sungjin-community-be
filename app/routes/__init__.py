from fastapi import APIRouter

from app.routes.auth import router as auth_router
from app.routes.comments import router as comments_router
from app.routes.images import router as images_router
from app.routes.messages import router as messages_router
from app.routes.notifications import router as notifications_router
from app.routes.posts import router as posts_router
from app.routes.social import router as social_router
from app.routes.users import router as users_router

router = APIRouter()

router.include_router(users_router)
router.include_router(auth_router)
router.include_router(posts_router)
router.include_router(comments_router)
router.include_router(images_router)
router.include_router(messages_router)
router.include_router(notifications_router)
router.include_router(social_router)
