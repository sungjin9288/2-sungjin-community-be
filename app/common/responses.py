from typing import Any
from fastapi.responses import JSONResponse


def ok(message: str, data: Any = None) -> JSONResponse:
    return JSONResponse(status_code=200, content={"message": message, "data": data})


def created(message: str, data: Any = None) -> JSONResponse:
    return JSONResponse(status_code=201, content={"message": message, "data": data})


def bad_request(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"message": message, "data": None})


def unauthorized(message: str = "unauthorized") -> JSONResponse:
    return JSONResponse(status_code=401, content={"message": message, "data": None})


def forbidden(message: str = "permission_denied") -> JSONResponse:
    return JSONResponse(status_code=403, content={"message": message, "data": None})


def not_found(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"message": message, "data": None})


def conflict(message: str) -> JSONResponse:
    return JSONResponse(status_code=409, content={"message": message, "data": None})


def server_error() -> JSONResponse:
    return JSONResponse(status_code=500, content={"message": "internal_server_error", "data": None})
