from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from app.routes import router as api_router
from app.common.responses import bad_request, server_error
from app.common.errors import INVALID_REQUEST, INTERNAL_SERVER_ERROR

app = FastAPI(title="Community API")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
 
    return bad_request(INVALID_REQUEST.message)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
  
    return server_error(INTERNAL_SERVER_ERROR.message)


app.include_router(api_router)
