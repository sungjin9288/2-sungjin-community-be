from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.routes import router as api_router
from app.common.exceptions import BusinessException, ErrorCodes

app = FastAPI()

# 1. 비즈니스 로직 예외 처리
@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "error": {"code": exc.code, "message": exc.message},
            "data": None
        }
    )

# 2. 예상치 못한 서버 에러 처리 (500)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"!!! Unhandled Server Error: {exc}") # 로그 남기기
    code, msg, status = ErrorCodes.INTERNAL_SERVER_ERROR
    return JSONResponse(
        status_code=status,
        content={
            "success": False,
            "message": msg,
            "error": {"code": code, "message": msg},
            "data": None
        }
    )

app.include_router(api_router)