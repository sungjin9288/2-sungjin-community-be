# 커뮤니티 백엔드 API

FastAPI 기반 커뮤니티 백엔드 프로젝트

## 📋 프로젝트 개요

- **목적**: Route - Controller - Model 패턴 학습
- **특징**: DB 없이 In-Memory 저장소 사용
- **인증**: 세션 쿠키 방식

## 🏗️ 아키텍처

```
app/
├── common/         # 공통 모듈 (인증, 예외, 응답 등)
├── models/         # 데이터 계층 (In-Memory 저장소)
├── controllers/    # 비즈니스 로직
├── routes/         # API 엔드포인트
└── main.py         # 앱 진입점
```

## 🚀 시작하기

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 서버 실행

```bash
# 개발 모드 (hot reload)
uvicorn app.main:app --reload

# 또는
python -m app.main
```

서버: http://localhost:8000  
API 문서: http://localhost:8000/docs

## 📡 API 엔드포인트

### 인증 (Auth)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | /auth/login | 로그인 |
| POST | /auth/logout | 로그아웃 |

### 사용자 (Users)

| Method | Endpoint | 설명 | 인증 |
|--------|----------|------|------|
| POST | /users/signup | 회원가입 | ❌ |
| GET | /users/me | 내 정보 조회 | ✅ |
| PUT | /users/me | 회원정보 수정 | ✅ |
| PUT | /users/me/password | 비밀번호 변경 | ✅ |
| DELETE | /users/me | 회원 탈퇴 | ✅ |

### 게시글 (Posts)

| Method | Endpoint | 설명 | 인증 |
|--------|----------|------|------|
| GET | /posts | 목록 조회 | ❌ |
| POST | /posts | 작성 | ✅ |
| GET | /posts/{id} | 상세 조회 | ❌ |
| PUT | /posts/{id} | 수정 | ✅ |
| DELETE | /posts/{id} | 삭제 | ✅ |
| POST | /posts/{id}/likes | 좋아요 | ✅ |
| DELETE | /posts/{id}/likes | 좋아요 취소 | ✅ |

### 댓글 (Comments)

| Method | Endpoint | 설명 | 인증 |
|--------|----------|------|------|
| GET | /posts/{id}/comments | 목록 조회 | ❌ |
| POST | /posts/{id}/comments | 작성 | ✅ |
| DELETE | /posts/{id}/comments/{cid} | 삭제 | ✅ |

## 🔐 보안

- **비밀번호 해싱**: PBKDF2-SHA256 (200,000 iterations)
- **세션 관리**: 쿠키 기반 (HttpOnly, SameSite=Lax)
- **입력 검증**: Pydantic 모델 + 커스텀 검증

## 📝 응답 형식

### 성공

```json
{
  "message": "success",
  "data": { ... }
}
```

### 에러

```json
{
  "message": "error_code",
  "data": null
}
```

## ✅ 구현된 기능

- [x] 회원가입 / 로그인 / 로그아웃
- [x] 게시글 CRUD
- [x] 댓글 CRUD
- [x] 좋아요 기능
- [x] 페이지네이션
- [x] 권한 체크
- [x] 입력 검증
- [x] 예외 처리
- [x] 로깅

## 🎯 실무 학습 포인트

### 아키텍처 패턴
- **계층 분리**: Route → Controller → Model
- **의존성 주입**: 재사용 가능한 인증 체커
- **예외 처리**: 커스텀 예외 + 전역 핸들러

### 보안
- 비밀번호 해싱 (평문 저장 금지)
- 세션 관리 (쿠키 보안 설정)
- 권한 체크 (작성자 검증)

### 코드 품질
- 타입 힌팅
- Docstring
- 검증 로직 분리
- 원본 데이터 보호 (copy 사용)

## 🚧 개선 가능 사항

- [ ] JWT 인증 전환
- [ ] 세션 만료 처리
- [ ] 데이터베이스 연동
- [ ] 단위 테스트 추가
- [ ] API 레이트 리미팅

## 📚 학습 자료

- FastAPI 공식 문서: https://fastapi.tiangolo.com
- Pydantic: https://docs.pydantic.dev
- REST API 설계: https://restfulapi.net

## 👨‍💻 개발자

- 성진
- GitHub Organization: 80-hours-a-week