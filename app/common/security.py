import bcrypt
import logging

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:

    try:
        # 입력값 검증
        if not plain_password or not hashed_password:
            logger.warning("비밀번호 검증: 빈 값 입력")
            return False
        
        # bcrypt 검증
        result = bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
        
        if not result:
            logger.info("비밀번호 검증: 일치하지 않음")
        
        return result
        
    except ValueError as e:
        # 잘못된 해시 형식
        logger.error(f"비밀번호 검증 실패 (ValueError): {e}")
        return False
        
    except Exception as e:
        # 기타 예외
        logger.error(f"비밀번호 검증 중 예외 발생: {type(e).__name__} - {e}")
        return False