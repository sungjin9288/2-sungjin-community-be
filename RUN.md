# 🚀 실행 가이드

## 1. 환경 설정

### Python 버전
- Python 3.10 이상 권장

### 가상환경 생성 (권장)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

## 2. 의존성 설치

```bash
pip install -r requirements.txt
```

## 3. 서버 실행

### 방법 1: uvicorn 직접 실행 (권장)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- `--reload`: 코드 변경 시 자동 재시작 (개발용)
- `--host 0.0.0.0`: 모든 네트워크 인터페이스에서 접속 허용
- `--port 8000`: 포트 번호

### 방법 2: Python 모듈로 실행

```bash
python -m app.main
```

## 4. 접속 확인

### API 문서 (Swagger UI)
```
http://localhost:8000/docs
```

### 대체 문서 (ReDoc)
```
http://localhost:8000/redoc
```

### 헬스 체크
```bash
curl http://localhost:8000/health
```

## 5. Postman 테스트

### 회원가입
```json
POST http://localhost:8000/users/signup

{
  "email": "test@example.com",
  "password": "password123",
  "nickname": "테스터"
}
```

### 로그인
```json
POST http://localhost:8000/auth/login

{
  "email": "test@example.com",
  "password": "password123"
}
```

**중요**: 로그인 후 쿠키가 자동으로 설정됩니다.  
Postman에서 "Send and download" 대신 일반 "Send" 사용해야 쿠키가 유지됩니다.

### 게시글 작성 (인증 필요)
```json
POST http://localhost:8000/posts

{
  "title": "첫 게시글",
  "content": "안녕하세요!"
}
```

## 6. 개발 팁

### 로그 확인
서버 실행 터미널에서 실시간 로그 확인 가능:
```
INFO:     Request: POST /users/signup
INFO:     Response: 201
```

### 데이터 초기화
서버 재시작 시 모든 데이터 초기화 (In-Memory 저장소)

### 디버깅
- FastAPI 자동 문서 활용: `/docs`
- 에러 발생 시 터미널에서 스택 트레이스 확인

## 7. 트러블슈팅

### 포트 이미 사용 중
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:8000 | xargs kill -9
```

### 쿠키가 안 넘어감 (Postman)
- "Settings" → "Cookies" → "Whitelist" 확인
- 또는 Header에 수동 추가: `Cookie: session_id=xxx`

### CORS 에러 (브라우저에서 테스트 시)
main.py에 CORS 미들웨어 추가:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 8. 프로덕션 배포 (참고)

```bash
# 프로덕션 모드 (--reload 제거)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 환경 변수 설정
```bash
# .env 파일 생성
SECRET_KEY=your-secret-key
ENVIRONMENT=production
```

### Gunicorn 사용 (Linux)
```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```
---

## 2026 Updated Runbook

### Environment Variables (recommended)

```bash
# Database
DATABASE_URL=sqlite:///./community.db

# App behavior
AUTO_CREATE_TABLES=true
CORS_ALLOW_ORIGINS=http://localhost:3001,http://127.0.0.1:3001

# Session cookie
SESSION_COOKIE_NAME=session_id
SESSION_COOKIE_MAX_AGE=604800
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_SAMESITE=lax
```

### Alembic Migration

```bash
pip install -r requirements.txt
alembic upgrade head
```

### Run Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Regression Tests

```bash
python -m pytest -q
```

### Existing DB Migration Baseline

If your DB already has tables from `create_all`, run:

```bash
alembic stamp 20260211_000001
```

Then continue with future migrations using:

```bash
alembic upgrade head
```

### JWT Auth Usage

Login and receive tokens:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"Abcd1234!"}'
```

Use access token:

```bash
curl http://localhost:8000/users/me \
  -H "Authorization: Bearer <access_token>"
```

Refresh token:

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'
```
