
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.routes import router as api_router
from app.common.exceptions import BusinessException, ErrorCodes
from app.common.responses import fail

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="커뮤니티 API",
    description="아무 말 대잔치 - FastAPI 기반 커뮤니티 백엔드",
    version="1.0.0"
)


# ==================== 예외 핸들러 ====================

@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):

    logger.warning(
        f"Business exception: {exc.code}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error_message": exc.message,  # ✅ 'message' 대신 'error_message'
            "status_code": exc.status_code
        }
    )
    return fail(exc.status_code, exc.message, exc.data)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):

    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "client": request.client.host if request.client else "unknown",
        },
        exc_info=True  # 스택 트레이스 포함
    )
    
    code, msg, status = ErrorCodes.INTERNAL_SERVER_ERROR
    return fail(status, msg, None)


# ==================== 미들웨어 ====================

@app.middleware("http")
async def log_requests(request: Request, call_next):
 
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response


# ==================== 라우터 등록 ====================

app.include_router(api_router)


# ==================== 헬스 체크 ====================

@app.get("/health")
def health_check():
 
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)