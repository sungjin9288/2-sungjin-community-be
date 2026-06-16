# Community Backend Repository Rules

Portfolio-grade FastAPI + SQLAlchemy backend for a community service.

This repo is one half of a larger product with `/Users/sungjin/dev/personal/2-sungjin-community-fe`.
Treat backend and frontend as one product split across sibling repos.

## Purpose

This repository demonstrates:
- API implementation
- database abstraction
- authentication
- runtime health behavior
- containerization and deployment portability

The code is not only a CRUD sample. Preserve both application behavior and delivery portability.

## Read Order

1. `README.md`
2. `requirements.txt`
3. `app/main.py`
4. `app/database.py`

## Core Rules

- Preserve database configurability through environment variables.
- Keep `/health` as a real database connectivity check.
- Preserve runtime directory bootstrap and static/uploads mounting behavior.
- Avoid changes that optimize for one deployment target at the cost of others unless explicitly requested.
- Prefer narrow, verifiable diffs over broad restructuring.
- If API contracts, auth, uploads, or health behavior change, consider frontend assumptions in the sibling repo.

## High-Risk Areas

- auth and token flows
- uploads/static path behavior
- database initialization
- deployment entrypoints
- environment-driven runtime branching

## Approval Boundaries

- schema/data migrations
- destructive or irreversible changes
- new production dependencies

## Verification

Run the most relevant backend verification available for the touched scope.
If deployment-specific validation was not re-run, state that explicitly at the end.

## Final Output

- changed files
- why
- commands run
- verification
- remaining risks or unverified deployment paths
- sibling repo follow-up if frontend work is implied but not included

---

## README 정직성 규칙 (포트폴리오 공개용 — 반드시 준수)

이 repo의 README는 채용 담당자·외부 방문자가 본다. README를 생성·수정할 때 아래를 **절대 규칙**으로 지킨다. 규칙을 어기면 작업을 멈추고 보고한다.

### 금지

- **측정 근거를 한 줄로 댈 수 없는 수치는 쓰지 않는다.** (예: "99.8% 비용 절감", "94.2% 자동화", "정확도 95%", "요청당 €0.0005")
  - 숫자를 쓰려면 **어떻게 쟀는지**(측정 커맨드·로그·방법)를 같은 자리에 표기한다. 못 대면 **삭제**한다.
- **과장 표현 금지**: "production-ready", "enterprise", "상용 운영", "엔터프라이즈". 실제가 PoC/MVP면 그대로 표기한다.
- 코드에 **없는** 기능·엔드포인트·성과를 적지 않는다. 추측 금지.

### 필수

- **테스트 수는 실제 코드로 카운트**해서 적고, 카운트 커맨드를 함께 둔다.
  - 예: `grep -rE "def test_" tests | wc -l`, `grep -rE "\b(test|it)\(" --include="*.test.*" | wc -l`
  - "정의된 함수 수"와 "통과 수"를 구분한다. 실제로 돌리지 않았으면 **"정의 기준 카운트, pass 여부는 별도 확인"**으로 표기.
- **엔드포인트·환경변수·디렉터리 구조는 코드/`.env.example`에서 직접 추출**한다. 손으로 지어내지 않는다.
- **`## Scope & Limitations` 섹션을 반드시 둔다.** 미구현·미검증·외부 의존·범위 밖 항목을 명시한다.
- **Demo·운영 URL은 접근 검증된 것만 링크**한다. 미검증이면 "(접근 검증 필요)"로 표기한다.

### 표준 구조

제목 → 한 줄 소개 → Why I Built This → Features → Tech Stack → Architecture → Key Design Decisions → Getting Started → (API/Usage) → Testing → Scope & Limitations → Links

### 갱신 절차

1. README를 고치기 전에 위 규칙을 먼저 적용한다.
2. 수정 후 **측정 근거 없는 새 수치가 들어가지 않았는지** 스스로 검사한다 (`99.8`, `production-ready` 등 grep).
3. 큰 변경은 "어디를 왜 바꿨는지"를 커밋 메시지/PR에 남긴다.
