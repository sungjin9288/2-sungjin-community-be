from typing import Any
from fastapi.responses import JSONResponse

def _body(success: bool, data: Any = None, message: str = None) -> dict:
    return {
        "success": success,
        "message": message,
        "data": data,
    }

def ok(message: str = "success", data: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=200, 
        content=_body(True, data, message)
    )

def created(message: str = "created", data: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=201, 
        content=_body(True, data, message)
    )