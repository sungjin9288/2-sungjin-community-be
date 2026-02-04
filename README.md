
# 🎭 아무 말 대잔치 - 커뮤니티 백엔드
### FastAPI 기반 RESTful API 커뮤니티 백엔드 서버

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)
![bcrypt](https://img.shields.io/badge/Security-bcrypt-525252?style=flat)

---

## 📋 목차
1. [프로젝트 소개](#-프로젝트-소개)
2. [주요 기능](#-주요-기능)
3. [기술 스택](#%EF%B8%8F-기술-스택)
4. [프로젝트 구조](#-프로젝트-구조)
5. [설치 및 실행](#-설치-및-실행)
6. [API 문서](#-api-문서)
7. [보안](#-보안)
8. [실무 적용 사항](#-실무-적용-사항)
9. [라이선스](#-라이선스)

---

## 🎯 프로젝트 소개
**아무 말 대잔치**는 사용자들이 자유롭게 소통할 수 있는 커뮤니티 플랫폼입니다.

### 프로젝트 목표
- ✅ **RESTful API 설계 원칙 준수**
- ✅ **계층 분리 아키텍처 구현** (Route-Controller-Model)
- ✅ **실무 수준의 보안 및 에러 처리**
- ✅ **체계적인 문서화**

---

## ✨ 주요 기능

### 🔐 인증 & 회원 관리
- **회원가입 / 로그인 / 로그아웃**
- **bcrypt 비밀번호 암호화**
- **쿠키 기반 세션 인증**
- 프로필 이미지 업로드
- 회원정보 수정 / 비밀번호 변경

### 📝 게시글 관리
- **게시글 CRUD** (생성, 조회, 수정, 삭제)
- **페이지네이션** (page, limit)
- 조회수 자동 증가
- 작성자 검증

### 💬 댓글 시스템
- 댓글 작성 / 조회 / 수정 / 삭제
- 게시글별 댓글 목록
- 작성자 검증

### ❤️ 좋아요 기능
- 좋아요 / 좋아요 취소
- 중복 좋아요 방지
- 좋아요 수 집계

### 🖼️ 이미지 업로드
- 프로필 이미지 업로드
- 게시글 이미지 업로드
- **파일 확장자 검증**
- **UUID 기반 파일명 생성**

### 📄 정적 페이지
- 이용약관 HTML 서빙
- 개인정보처리방침 HTML 서빙

---

## 🛠️ 기술 스택

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI 0.115+
- **Server**: Uvicorn (ASGI 서버)

### Security
- **Hashing**: bcrypt (비밀번호 해싱)
- **Session**: HttpOnly Cookies (XSS 방어), SameSite Cookies (CSRF 방어)

### Storage
- **Database**: In-Memory (개발 환경 - JSON 데이터)
- **File System**: Local Storage (이미지 저장)

### Development
- **Validation**: Pydantic (데이터 검증)
- **Logging**: Python Logging (구조화된 로그)

---

## 📁 프로젝트 구조

```bash
2-sungjin-community-be/
├── app/
│   ├── common/                 # 공통 모듈
│   │   ├── __init__.py
│   │   ├── auth.py            # 인증 헬퍼
│   │   ├── deps.py            # 의존성 주입
│   │   ├── exceptions.py      # 커스텀 예외
│   │   ├── responses.py       # 응답 포맷
│   │   └── security.py        # 비밀번호 해싱
│   │
│   ├── controllers/            # 비즈니스 로직
│   │   ├── __init__.py
│   │   ├── auth_controller.py
│   │   ├── users_controller.py
│   │   ├── posts_controller.py
│   │   └── comments_controller.py
│   │
│   ├── models/                 # 데이터 모델
│   │   ├── __init__.py
│   │   ├── users_model.py
│   │   ├── posts_model.py
│   │   └── comments_model.py
│   │
│   ├── routes/                 # API 라우터
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── posts.py
│   │   ├── comments.py
│   │   └── images.py
│   │
│   └── main.py                 # 애플리케이션 진입점
│
├── static/                     # 정적 파일
│   ├── uploads/               # 업로드된 이미지
│   └── terms/                 # 이용약관 HTML
│       ├── service.html
│       └── privacy.html
│
├── requirements.txt            # Python 의존성
├── .gitignore
├── README.md
├── RUN.md                      # 실행 가이드
└── CHANGELOG.md                # 변경 이력
```

---

## 🚀 설치 및 실행

### 1. 저장소 클론
```bash
git clone https://github.com/sungjin9288/2-sungjin-community-be.git
cd 2-sungjin-community-be
```

### 2. 가상환경 생성 및 활성화
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```
*`requirements.txt` 주요 패키지:*
- `fastapi`
- `uvicorn[standard]`
- `pydantic`
- `python-multipart`
- `bcrypt`

### 4. 서버 실행
```bash
# 개발 모드 (자동 재시작)
uvicorn app.main:app --reload

# 프로덕션 모드
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 5. 서버 확인
- ✅ **서버**: `http://localhost:8000`
- 📖 **API 문서**: `http://localhost:8000/docs`
- 📊 **Redoc 문서**: `http://localhost:8000/redoc`

---

## 📖 API 문서

### Swagger UI
`http://localhost:8000/docs`
- 모든 API 엔드포인트 확인
- 실시간 테스트 가능
- 요청/응답 스키마 확인

### API 엔드포인트 요약

#### 🔐 인증 (Auth)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| POST | `/auth/login` | 로그인 |
| POST | `/auth/logout` | 로그아웃 |

#### 👤 회원 (Users)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| POST | `/users/signup` | 회원가입 |
| GET | `/users/me` | 내 정보 조회 |
| PUT | `/users/me` | 회원정보 수정 |
| PUT | `/users/me/password` | 비밀번호 변경 |
| DELETE | `/users/me` | 회원 탈퇴 |

#### 📝 게시글 (Posts)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/posts` | 게시글 목록 (페이지네이션) |
| POST | `/posts` | 게시글 작성 |
| GET | `/posts/{post_id}` | 게시글 상세 조회 |
| PUT | `/posts/{post_id}` | 게시글 수정 |
| DELETE | `/posts/{post_id}` | 게시글 삭제 |
| POST | `/posts/{post_id}/likes` | 좋아요 |
| DELETE | `/posts/{post_id}/likes` | 좋아요 취소 |

#### 💬 댓글 (Comments)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/posts/{post_id}/comments` | 댓글 목록 |
| POST | `/posts/{post_id}/comments` | 댓글 작성 |
| PUT | `/comments/{comment_id}` | 댓글 수정 |
| DELETE | `/comments/{comment_id}` | 댓글 삭제 |

#### 🖼️ 이미지 (Images)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| POST | `/images/profile` | 프로필 이미지 업로드 |
| POST | `/images/post` | 게시글 이미지 업로드 |

### API 응답 예시
**성공 응답:**
```json
{
  "message": "signup_success",
  "data": {
    "id": 1,
    "email": "user@example.com",
    "nickname": "사용자"
  }
}
```

**에러 응답:**
```json
{
  "message": "email_already_exists",
  "data": null
}
```

---

## 🔒 보안 (Security)

### 비밀번호 보안
- **bcrypt 해싱 알고리즘** 사용
- `rounds=12` (업계 표준)
- 72바이트 제한 처리
```python
import bcrypt

# 해싱
salt = bcrypt.gensalt(rounds=12)
hashed = bcrypt.hashpw(password.encode('utf-8'), salt)

# 검증
is_valid = bcrypt.checkpw(password.encode('utf-8'), hashed)
```

### 세션 보안
- **HttpOnly 쿠키** (JavaScript 접근 불가)
- **SameSite=lax** (CSRF 공격 방어)
- UUID v4 기반 세션 ID
- 7일 만료 시간 설정

### 파일 업로드 보안
- **파일 확장자 검증** (`.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`)
- **UUID 기반 고유 파일명**으로 저장 (파일명 충돌 및 조작 방지)

### 입력 검증
- 이메일 형식 검증
- 비밀번호 복잡도 정책 (8자 이상)
- 닉네임 길이 제한 (2-10자)
- 페이지네이션 범위 검증

---

## 💼 실무 적용 사항 (Best Practices)

### 1. 아키텍처 패턴
- **Route-Controller-Model 3계층 분리**를 통해 유지보수성 향상
- **의존성 주입 (Dependency Injection)** 활용
- **관심사 분리 (Separation of Concerns)** 원칙 준수

### 2. 코드 품질
- **Type Hints** 적극 사용으로 개발 생산성 향상
- **Docstrings** 작성을 통한 문서화
- **일관된 에러 처리 (try-except)** 및 커스텀 예외 클래스 사용
- **DRY (Don't Repeat Yourself)** 원칙 준수

### 3. 로깅 시스템
```python
import logging
logger = logging.getLogger(__name__)

# 구조화된 로그
logger.info(
    f"Request: {method} {path}",
    extra={"user_id": user_id, "status": 200}
)
```

### 4. Git 커밋 규칙 (Conventional Commits)
- `feat`: 새로운 기능 추가
- `fix`: 버그 수정
- `refactor`: 코드 리팩토링
- `docs`: 문서 수정
- `test`: 테스트 추가
- `chore`: 설정 등 기타 작업

---

## 📚 학습 포인트

### 백엔드 개발
- ✅ RESTful API 설계
- ✅ 비동기 프로그래밍 (async/await)
- ✅ 인증/인가 구현 (Session/Cookie)
- ✅ 파일 업로드 처리
- ✅ 데이터 검증 (Pydantic)

### 보안
- ✅ 비밀번호 해싱 (bcrypt)
- ✅ 세션 관리 보안 (HttpOnly, SameSite)
- ✅ XSS/CSRF 방어 고려
- ✅ 입력값 검증

### 아키텍처
- ✅ 계층 분리 패턴
- ✅ 의존성 주입 (DI)
- ✅ 에러 핸들링 전략
- ✅ 로깅 시스템 구축

---

## 🙏 감사의 말
이 프로젝트를 통해 백엔드 개발의 전반적인 흐름과 보안, 아키텍처의 중요성을 깊이 이해할 수 있었습니다.

---
Copyright © 2026 Sungjin An. All rights reserved.
