from fastapi import APIRouter, Request, UploadFile, File
from pathlib import Path
import uuid
import logging

from app.common import responses
from app.common.deps import require_user_id
from app.common.exceptions import BusinessException, ErrorCode

router = APIRouter(prefix="/images", tags=["images"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


async def _save_upload_file(file: UploadFile, subdir: str) -> str:
    """파일 유효성 검사 후 저장하고 public URL을 반환합니다."""
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise BusinessException(
            ErrorCode.INVALID_REQUEST_FORMAT,
            f"허용되지 않는 파일 형식입니다. 허용: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise BusinessException(
            ErrorCode.INVALID_REQUEST_FORMAT,
            f"파일 크기는 {MAX_FILE_SIZE // (1024 * 1024)}MB 이하여야 합니다.",
        )

    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = UPLOAD_DIR / subdir / unique_filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(content)

    image_url = f"/uploads/{subdir}/{unique_filename}"
    logger.info("이미지 업로드 성공: %s", image_url)
    return image_url


@router.post("/profile")
async def upload_profile_image(request: Request, file: UploadFile = File(...)):
    require_user_id(request)
    image_url = await _save_upload_file(file, "profile")
    return responses.ok("upload_success", {"image_url": image_url})


@router.post("/post")
async def upload_post_image(request: Request, file: UploadFile = File(...)):
    require_user_id(request)
    image_url = await _save_upload_file(file, "post")
    return responses.ok("upload_success", {"image_url": image_url})