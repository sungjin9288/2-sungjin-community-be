from fastapi import FastAPI
from app.routes import users, posts, comments

app = FastAPI(title="Community API")

app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(posts.router, prefix="/posts", tags=["Posts"])
app.include_router(comments.router, tags=["Comments"])
