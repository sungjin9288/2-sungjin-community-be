from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import uuid
import logging

from app.common import responses

router = APIRouter(prefix="/images", tags=["images"])
logger = logging.getLogger(__name__)

# 업로드 디렉토리 (static에서 분리)
UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/profile")
async def upload_profile_image(file: UploadFile = File(...)):

    try:
        # 파일 확장자 검증
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"허용되지 않는 파일 형식입니다. 허용: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # 파일 크기 검증
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"파일 크기는 {MAX_FILE_SIZE // (1024*1024)}MB 이하여야 합니다"
            )
        
        # 고유 파일명 생성
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = UPLOAD_DIR / "profile" / unique_filename
        
        # 파일 저장
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(content)
        
        # URL 반환 (uploads 경로 사용)
        image_url = f"/uploads/profile/{unique_filename}"
        
        logger.info(f"프로필 이미지 업로드 성공: {image_url}")
        
        return responses.success({
            "image_url": image_url,
            "filename": unique_filename
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이미지 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail="이미지 업로드에 실패했습니다")


@router.post("/post")
async def upload_post_image(file: UploadFile = File(...)):

    try:
        # 파일 확장자 검증
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"허용되지 않는 파일 형식입니다. 허용: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # 파일 크기 검증
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"파일 크기는 {MAX_FILE_SIZE // (1024*1024)}MB 이하여야 합니다"
            )
        
        # 고유 파일명 생성
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = UPLOAD_DIR / "post" / unique_filename
        
        # 파일 저장
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(content)
        
        # URL 반환 (uploads 경로 사용)
        image_url = f"/uploads/post/{unique_filename}"
        
        logger.info(f"게시글 이미지 업로드 성공: {image_url}")
        
        return responses.success({
            "image_url": image_url,
            "filename": unique_filename
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이미지 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail="이미지 업로드에 실패했습니다")