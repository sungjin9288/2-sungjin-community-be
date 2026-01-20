
from fastapi import APIRouter, UploadFile, File, Request
from pathlib import Path
import shutil
import uuid
from app.common.exceptions import BusinessException, ErrorCodes
from app.common.deps import require_user_id

router = APIRouter(prefix="/images", tags=["images"])


UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


MAX_FILE_SIZE = 5 * 1024 * 1024


def validate_image_file(file: UploadFile) -> None:

    if not file.filename:
        raise BusinessException(
            "invalid_file",
            "파일명이 없습니다.",
            400
        )
    
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in ALLOWED_EXTENSIONS:
        raise BusinessException(
            "invalid_file_type",
            f"지원하지 않는 파일 형식입니다. 허용: {', '.join(ALLOWED_EXTENSIONS)}",
            400,
            data={"allowed_extensions": list(ALLOWED_EXTENSIONS)}
        )


def save_upload_file(file: UploadFile) -> str:

    file_ext = Path(file.filename).suffix.lower()
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = UPLOAD_DIR / unique_filename
    
  
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise BusinessException(
            "file_save_error",
            "파일 저장 중 오류가 발생했습니다.",
            500
        )
    finally:
        file.file.close()
    
  
    return f"/static/uploads/{unique_filename}"


@router.post("/profile")
async def upload_profile_image(
    request: Request,
    file: UploadFile = File(...)
):


    user_id = require_user_id(request)
    

    validate_image_file(file)
    

    image_url = save_upload_file(file)
    
    return {
        "message": "image_uploaded",
        "data": {"image_url": image_url}
    }


@router.post("/post")
async def upload_post_image(
    request: Request,
    file: UploadFile = File(...)
):

 
    user_id = require_user_id(request)
    

    validate_image_file(file)
    
  
    image_url = save_upload_file(file)
    
    return {
        "message": "image_uploaded",
        "data": {"image_url": image_url}
    }