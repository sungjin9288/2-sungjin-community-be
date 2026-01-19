
from fastapi import APIRouter, Request
from app.controllers import users_controller
from app.common.deps import require_user_id

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/signup")
def signup(payload: dict):

    return users_controller.signup(payload)


@router.get("/me")
def get_me(request: Request):

    user_id = require_user_id(request)
    return users_controller.get_me(user_id)


@router.put("/me")
def update_me(payload: dict, request: Request):

    user_id = require_user_id(request)
    return users_controller.update_me(user_id, payload)


@router.put("/me/password")
def update_password(payload: dict, request: Request):

    user_id = require_user_id(request)
    return users_controller.update_password(user_id, payload)


@router.delete("/me")
def withdraw(request: Request):

    user_id = require_user_id(request)
    return users_controller.withdraw(user_id)