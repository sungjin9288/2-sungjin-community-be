from fastapi import APIRouter, Header
from app.controllers import users_controller

router = APIRouter()

@router.post("/signup")
def signup(payload: dict):
    return users_controller.signup(payload)

@router.post("/login")
def login(payload: dict):
    return users_controller.login(payload)

@router.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    return users_controller.logout(authorization)
