import re
from fastapi.responses import JSONResponse
from app.common.responses import ok, created
from app.common.exceptions import (
    BusinessException, ErrorCode,
    MissingRequiredFieldsError, InvalidRequestFormatError,
    InvalidEmailFormatError, EmailAlreadyExistsError, 
    NicknameAlreadyExistsError, UserNotFoundError, 
    InvalidCredentialsError, InvalidPasswordError
)
from app.common.security import hash_password, verify_password
from app.models import users_model


def _validate_email(email: str) -> bool:
    # 이메일 형식: example@adapterz.kr 등
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def _validate_nickname(nickname: str) -> None:
    # 1. 띄어쓰기 확인 (기획서: "띄어쓰기불가")
    if ' ' in nickname:
        raise BusinessException(
            ErrorCode.INVALID_REQUEST_FORMAT,
            "닉네임에 띄어쓰기를 없애주세요"
        )
    
    # 2. 길이 확인 (기획서: "10글자 이내")
    if len(nickname) < 1: # 최소 길이 (빈 값은 상위에서 체크하지만 안전장치)
        raise MissingRequiredFieldsError("닉네임을 입력해주세요.")
        
    if len(nickname) > 10:
        raise BusinessException(
            ErrorCode.INVALID_REQUEST_FORMAT,
            "닉네임은 최대 10자 까지 작성 가능합니다."
        )


def _validate_password(password: str) -> None:
    # 기획서: 8자 이상, 20자 이하
    if len(password) < 8:
        raise BusinessException(
            ErrorCode.PASSWORD_TOO_SHORT,
            "비밀번호는 8자 이상, 20자 이하이며, 대문자, 소문자, 숫자, 특수문자를 각각 최소 1개 포함해야 합니다."
        )
    
    if len(password) > 20:
        raise BusinessException(
            ErrorCode.PASSWORD_TOO_LONG,
            "비밀번호는 8자 이상, 20자 이하이며, 대문자, 소문자, 숫자, 특수문자를 각각 최소 1개 포함해야 합니다."
        )

    # 기획서: 대문자, 소문자, 숫자, 특수문자 각각 최소 1개 포함
    # (?=.*[a-z]) : 소문자 적어도 1개
    # (?=.*[A-Z]) : 대문자 적어도 1개
    # (?=.*\d)    : 숫자 적어도 1개
    # (?=.*[@$!%*?&]) : 특수문자 적어도 1개 (여기서는 일반적인 특수문자 예시 사용)
    pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,20}$'
    
    if not re.match(pattern, password):
        raise InvalidPasswordError(
            "비밀번호는 대문자, 소문자, 숫자, 특수문자를 각각 최소 1개 포함해야 합니다."
        )


def check_email(payload: dict) -> JSONResponse:
    email = (payload.get("email") or "").strip()
    
    if not email:
        raise MissingRequiredFieldsError("이메일을 입력해주세요.")
    
    if not _validate_email(email):
        raise InvalidEmailFormatError("올바른 이메일 주소 형식을 입력해주세요.")
    
    if users_model.is_email_exists(email):
        return ok(
            message="email_already_exists",
            data={"available": False, "email": email}
        )
    
    return ok(
        message="email_available",
        data={"available": True, "email": email}
    )


def signup(payload: dict) -> JSONResponse:
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""
    nickname = (payload.get("nickname") or "").strip()
    profile_image_url = payload.get("profile_image_url")
    
    # 1. 필수 값 체크
    if not email:
        raise MissingRequiredFieldsError("이메일을 입력해주세요.")
    if not password:
        raise MissingRequiredFieldsError("비밀번호를 입력해주세요.")
    if not nickname:
        raise MissingRequiredFieldsError("닉네임을 입력해주세요.")
    
    # 기획서: "*프로필 사진을 추가해주세요" -> 선택 사항으로 변경 (2단계 업로드 플로우 지원)
    # 프로필 사진은 회원가입 후 업로드할 수 있음

    # 2. 유효성 검사 (Regex)
    if not _validate_email(email):
        raise InvalidEmailFormatError()

    _validate_nickname(nickname)
    _validate_password(password)

    # 3. 중복 검사
    if users_model.is_email_exists(email):
        raise EmailAlreadyExistsError("중복된 이메일 입니다.") # 기획서 문구 반영
    
    if users_model.is_nickname_exists(nickname):
        raise NicknameAlreadyExistsError("중복된 닉네임 입니다.") # 기획서 문구 반영

    # 4. 저장
    users_model.create_user(email, password, nickname, profile_image_url)
    return created(message="signup_success", data=None)


def get_me(user_id: int) -> JSONResponse:
    user = users_model.get_user_by_id(user_id)
    if not user:
        raise UserNotFoundError()

    data = {
        "id": user["id"],
        "email": user["email"],
        "nickname": user["nickname"],
        "profile_image_url": user.get("profile_image_url")
    }
    return ok(message="read_me_success", data=data)


def update_me(user_id: int, payload: dict) -> JSONResponse:
    user = users_model.get_user_by_id(user_id)
    if not user:
        raise UserNotFoundError()

    nickname = (payload.get("nickname") or "").strip()
    profile_image_url = payload.get("profile_image_url")

    # 닉네임 변경 시 유효성 및 중복 검사
    if nickname:
        _validate_nickname(nickname)
        if nickname != user["nickname"] and users_model.is_nickname_exists(nickname):
             raise NicknameAlreadyExistsError("중복된 닉네임 입니다.")

    updated = users_model.update_user(
        user_id,
        nickname=nickname or None,
        profile_image_url=profile_image_url
    )
    
    if not updated:
        raise UserNotFoundError()

    data = {
        "id": updated["id"],
        "email": updated["email"],
        "nickname": updated["nickname"],
        "profile_image_url": updated.get("profile_image_url")
    }
    return ok(message="user_updated", data=data)


def update_password(user_id: int, payload: dict) -> JSONResponse:
    old_pw = payload.get("old_password") or ""
    new_pw = payload.get("new_password") or ""

    if not new_pw:
        raise MissingRequiredFieldsError("새 비밀번호를 입력해주세요")

    user = users_model.get_user_by_id(user_id)
    if not user:
        raise UserNotFoundError()

    # 설계도: 현재 비밀번호 검증은 선택적 (빈 문자열이면 건너뜀)
    if old_pw and not verify_password(old_pw, user["password"]):
        raise InvalidCredentialsError("현재 비밀번호가 확인과 다릅니다.") 

    
    _validate_password(new_pw)

    users_model.update_user(user_id, password_hash=hash_password(new_pw))
    return ok(message="password_updated", data=None)


def withdraw(user_id: int) -> JSONResponse:
    user = users_model.get_user_by_id(user_id)
    if not user:
        raise UserNotFoundError()

    users_model.delete_user(user_id)
    return ok(message="user_deleted", data=None)