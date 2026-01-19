
from typing import Any, Optional
from fastapi.responses import JSONResponse


def ok(message: str = "success", data: Any = None) -> JSONResponse:
    """200 OK 응답"""
    return JSONResponse(
        status_code=200,
        content={"message": message, "data": data}
    )


def created(message: str = "created", data: Any = None) -> JSONResponse:
    """201 Created 응답"""
    return JSONResponse(
        status_code=201,
        content={"message": message, "data": data}
    )


def fail(status_code: int, message: str, data: Any = None) -> JSONResponse:
    """에러 응답"""
    return JSONResponse(
        status_code=status_code,
        content={"message": message, "data": data}
    )