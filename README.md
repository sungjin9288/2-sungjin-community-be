# Community Backend Portfolio | 아무 말 대잔치 Backend

## 프로젝트 개요 | Project Overview
`2-sungjin-community-be`는 **FastAPI + SQLAlchemy** 기반의 community backend API repository입니다.
이 저장소는 CRUD API 구현에만 머물지 않고, **database abstraction, authentication, containerization, Lambda image delivery, ECS rollout, EC2 deployment readiness, Kubernetes compatibility**까지 포함하도록 구성되었습니다.

This repository was developed as a portfolio-grade backend project. The focus was to demonstrate not only API implementation, but also how a backend can be packaged, verified, deployed, and operated across multiple runtime targets.

- Backend Repo: `https://github.com/sungjin9288/2-sungjin-community-be`
- Frontend Repo: `https://github.com/sungjin9288/2-sungjin-community-fe`
- Runtime note: cloud runtime resources used for validation were intentionally **torn down on 2026-03-11** to avoid unnecessary cost. The source code, deployment scripts, workflow definitions, and runbooks remain as portfolio evidence.

## 역할 정의 | Repository Role
This backend repository owns the following responsibilities:

| Area | Scope |
| --- | --- |
| API Layer | auth, users, posts, comments, direct messages, image-related endpoints, **restaurant chatbot** |
| Data Layer | SQLAlchemy models, session management, DB health check |
| Security | password hashing, token-based auth flow, request validation |
| Runtime | FastAPI app startup, static/uploads mounting, health endpoints |
| Delivery | Docker image build, ECS task deployment support, Lambda container image support |
| Verification | pytest regression coverage, health checks, deployment smoke readiness |
| **Recommendation** | **BM25 + user behavior log ranking engine** |
| **Chatbot** | **LangChain-based restaurant recommendation chatbot (Gemini / Ollama)** |

## 핵심 성과 | Key Outcomes
- Built a **FastAPI REST API** supporting the full community lifecycle.
- Added a **database-driven health check** so deployment targets can fail fast when DB connectivity is broken.
- Made the backend **database-configurable** through `DATABASE_URL`, enabling SQLite for local validation and MySQL/PostgreSQL-compatible drivers for deployment targets.
- Added **runtime directory bootstrap** so containerized startup does not fail when `uploads/` or `static/` paths are missing.
- Packaged the backend for multiple targets:
  - EC2 + Docker Compose
  - ECS Fargate
  - Lambda container image
  - Kubernetes-compatible container runtime
- Verified integration with the frontend repository and GitHub Actions delivery flows.
- **Implemented a restaurant recommendation chatbot** using LangChain + BM25 ranking based on real user behavior logs (7.1M rows).

## 기술 스택 | Tech Stack

### Application Layer
- `Python 3.11+`
- `FastAPI`
- `Uvicorn`
- `Pydantic`

### Data / Persistence
- `SQLAlchemy`
- `SQLite` for local/staging validation
- `PyMySQL` and `psycopg2-binary` for MySQL/PostgreSQL-compatible targets
- `Alembic` included in dependencies for migration-ready evolution

### Security / Auth
- `bcrypt`
- `passlib`
- `PyJWT`

### Chatbot / Recommendation *(추가)*
- `LangChain` — ConversationChain + ConversationBufferWindowMemory(k=5)
- `langchain-google-genai` — Gemini 2.0 Flash (무료 API)
- `langchain-ollama` — 로컬 Ollama (키 불필요)
- `rank_bm25` — BM25Okapi 검색 인덱스
- `kiwipiepy` — 한국어 형태소 분석
- `pandas` — 710만 행 로그 벡터 처리

### Delivery / Platform
- `Docker`
- `AWS ECS Fargate`
- `AWS Lambda (container image)`
- `AWS EC2`
- `Kubernetes-compatible deployment templates`

## 아키텍처 | Architecture

### Request path
1. Client sends request to FastAPI application.
2. Route layer validates request payload via Pydantic.
3. Controller/model layer executes business logic.
4. SQLAlchemy session accesses the configured database.
5. Response helpers return a consistent API envelope.

### Runtime-specific behavior
- `lifespan()` ensures startup/shutdown logging.
- `ensure_runtime_directories()` creates `uploads/`, `uploads/profile/`, `uploads/post/`, and `static/` before mounts.
- `/health` performs a real DB connectivity check using `SELECT 1`.
- `/uploads` and `/static` are mounted as static paths for image/content serving.
- **`RecommendationEngine.load()`** — on startup, loads `shops.csv` + `logs.csv` and builds a BM25 index and user behavior score maps in memory.
- **`ChatbotChain.initialize()`** — on startup, connects to the configured LLM provider (Gemini or Ollama).

## 주요 기능 | Functional Scope

### Authentication / 인증
- signup
- login
- token refresh
- logout
- email duplication check
- nickname duplication check

### User Management / 사용자 관리
- my profile read/update
- 1:1 direct message thread list/read/send
- password change
- account deletion

### Post Domain / 게시글
- create, read, update, delete
- pagination
- detail read with count-related handling
- likes integration

### Comment Domain / 댓글
- create, update, delete
- list by post
- author ownership checks

### Social / 소셜
- block / unblock users
- report posts, comments, users, messages
- bookmark / unbookmark posts
- notifications

### Static & Uploads / 정적 리소스
- terms/privacy static serving
- uploads mount for image delivery
- Lambda container entrypoint for image-oriented runtime packaging

### Restaurant Chatbot / 식당 추천 챗봇 *(신규)*
- `POST /chatbot/chat` — 식당 추천 챗봇 대화
- `POST /chatbot/chat/stream` — SSE 기반 스트리밍 응답
- `POST /chatbot/feedback` — 추천 카드 좋아요/별로예요/저장 피드백 반영
- `GET /chatbot/profile` — 세션별 장기 취향 프로필 조회
- `POST /chatbot/reset` — 대화 기록 초기화
- `GET /chatbot/status` — 추천 엔진 / LLM 초기화 상태 확인

## 식당 추천 챗봇 | Restaurant Recommendation Chatbot

### 아키텍처

```
POST /chatbot/chat
    ↓
ChatbotController
    ├── IntentRouter            (식당 추천 / 취향 프로필 / 계획된 커뮤니티 기능 분기)
    ├── PersonalizationStore   (DB-backed long-term preference memory)
    ├── RecommendationEngine   (BM25 + 행동 로그 + 개인화 랭킹)
    │     ├── kiwipiepy 형태소 분석
    │     ├── BM25Okapi 검색 (rank_bm25)
    │     └── 세션 기반 query 전파 + 이벤트 가중치 스코어링
    └── ChatbotChain           (LangChain)
          ├── Gemini 2.0 Flash (API)
          └── Ollama llama3.2  (로컬)
```

### 추천 모델 설계
- **BM25 인덱스**: `shop_name`, `address`, `categories`, `menus`, `facilities` 필드를 형태소 분석 후 인덱싱
- **행동 로그 랭킹**: 710만 행 logs.csv 를 pandas 벡터 연산으로 처리
  - 이벤트 가중치: `impression=0, click=1, view=2, bookmark=5, reservation=10`
  - 세션 내 `impression/click` → `bookmark/reservation` 으로 `search_query` 전파 (ffill)
  - `data/log_cache.pkl`이 있으면 서버 시작 시 사전 집계된 로그 인덱스를 로드
- **상황형 query 보정**: 토큰 단독 점수와 별도로 query phrase index를 두어 `성수 데이트`처럼 같이 등장한 검색 의도를 반영
- **결합 스코어**: `0.45 × BM25 + 0.40 × 의도로그 + 0.15 × 인기도`
- **개인화 결합 스코어**: `0.35 × BM25 + 0.30 × 의도로그 + 0.15 × 인기도 + 0.20 × 개인 취향`
- **장기 메모리**: 기본값은 SQLAlchemy DB의 `chatbot_memories` 테이블이며, `CHATBOT_MEMORY_BACKEND=memory` 설정 시 인메모리만 사용
- **계정 기반 취향 저장**: 로그인 사용자는 `user:{id}` 메모리 키로 저장되어 브라우저/기기 세션이 달라도 같은 취향 프로필을 사용
- **Intent 라우팅**: 식당 추천, 취향 프로필 조회, 향후 커뮤니티 보조 기능을 분리하여 식당 추천을 챗봇의 독립 기능으로 유지
- **피드백 루프**: 추천 카드의 좋아요/별로예요/저장 데이터를 프로필과 재랭킹에 반영
- **추가 질문 흐름**: 지역만 있는 요청처럼 조건이 부족하면 메뉴/상황을 먼저 질문
- **라면 맛집 의도 보정**: 오마카세 후식라면 매장은 '라면' 검색 로그에서 클릭·예약이 없으므로 의도 스코어가 낮아 자동 하위 랭크

### 추천 캐시 및 평가
```bash
# 710만 행 로그를 사전 집계해 서버 cold start를 줄임
python scripts/preprocess_logs.py --force

# 샘플 로그 기준 NDCG/MRR/HitRate/Coverage/latency 측정
python scripts/evaluate_recommendation.py \
  --max-rows 100000 \
  --max-queries 20 \
  --top-k 5 \
  --output data/recommendation_eval_report.json \
  --details-output data/recommendation_eval_details.jsonl

# 챗봇 피드백 로그를 랭킹 학습 샘플로 변환
python scripts/export_chatbot_learning_dataset.py \
  --input data/chatbot_learning_logs.jsonl \
  --output data/chatbot_training_samples.jsonl

# 초기 피드백이 부족하면 기존 행동 로그로 weak-label 학습 샘플 생성
python scripts/build_recommendation_training_dataset.py \
  --max-rows 500000 \
  --max-queries 200 \
  --candidate-k 50 \
  --output data/recommendation_training_samples.jsonl

# 학습 샘플로 개인화 랭킹 가중치 실험
python scripts/tune_chatbot_rank_weights.py \
  --input data/recommendation_training_samples.jsonl \
  --output data/chatbot_rank_weight_candidate.json \
  --top-k 5 \
  --step 0.1 \
  --min-groups 3

# 기준 성능보다 개선된 후보만 서버 적용 artifact로 승격
python scripts/promote_chatbot_rank_weights.py \
  --input data/chatbot_rank_weight_candidate.json \
  --output data/chatbot_rank_weight_report.json \
  --decision-output data/chatbot_rank_weight_decision.json \
  --metric ndcg \
  --min-samples 100 \
  --min-groups 3 \
  --min-improvement 0.0001
```

서버는 기본적으로 `data/chatbot_rank_weight_report.json`이 있으면 추천 가중치 artifact로 읽는다. 다른 경로를 쓰려면 `CHATBOT_RANK_WEIGHT_PATH=/path/to/report.json`을 지정한다. artifact가 없거나 `status != "ok"`이면 기존 기본 가중치로 fallback한다.

학습 데이터 수집과 모델 고도화 절차는 `docs/chatbot_ai_training_guide.md`를 참고한다.

### LLM 설정
`LLM_PROVIDER` 환경변수로 실시간 전환 가능:

| 값 | LLM | 준비 사항 |
|---|---|---|
| `gemini` | Google Gemini 2.0 Flash | `GOOGLE_API_KEY` 설정 |
| `ollama` | Ollama llama3.2 (로컬) | `ollama serve` 실행 |
| `mock` | 규칙 기반 응답 | 없음 |

### 대화 예시
```
[상황 1]
유저: 중구 평냉 맛집 좀 추천해줘
챗봇: 가격대는 어떤게 좋으세요?
유저: 너무 비싸지 않은 곳으로
챗봇: 강남에 ... (추천 결과)

[상황 2]
유저: 삼성전자 주가 좀 전망해줘
챗봇: 저는 식당 추천 봇입니다. 죄송하지만 식당 관련 질의해 주시겠어요?
```

## 현재 코드 기준 기술 포인트 | Implementation Notes

### Database configuration
`app/database.py` resolves the database from environment configuration:

```python
DEFAULT_SQLITE_URL = "sqlite:///./community.db"
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)
```

This means the same application can run:
- locally with SQLite
- in containerized validation with SQLite-backed volume
- in production-like environments with MySQL/PostgreSQL-compatible URLs

### Startup hardening
A deployment issue was fixed by ensuring runtime directories are created before `StaticFiles` mounts are initialized.

Relevant file:
- `app/main.py`

## 프로젝트 구조 | Repository Structure

```text
2-sungjin-community-be/
├── app/
│   ├── chatbot/                   # 식당 추천 챗봇 (신규)
│   │   ├── recommendation_engine.py  # BM25 + 행동 로그 랭킹 엔진
│   │   ├── chatbot_chain.py          # LangChain Gemini/Ollama 체인
│   │   └── chatbot_controller.py     # 오케스트레이션
│   ├── common/                    # shared helpers, response/exception utilities
│   ├── controllers/               # business logic orchestration
│   ├── core/                      # logging and shared runtime utilities
│   ├── models/                    # domain access layer
│   ├── routes/                    # FastAPI routers
│   │   └── chatbot.py             # /chatbot/* 엔드포인트 (신규)
│   ├── database.py                # engine / session configuration
│   ├── db_models.py               # SQLAlchemy ORM models
│   ├── lambda_handler.py          # Lambda container entrypoint
│   └── main.py                    # FastAPI application bootstrap
├── data/                          # CSV 데이터 (신규, .gitignore 처리)
│   ├── shops.csv                  # 매장 정보 (500개)
│   └── logs.csv                   # 사용자 행동 로그 (710만 행)
├── deploy/ecs/                    # ECS task definition template assets
├── scripts/                       # deployment helpers
├── tests/                         # pytest regression coverage
├── Dockerfile
├── Dockerfile.lambda
├── requirements.txt
└── README.md
```

## 로컬 실행 | Local Development

### Prerequisites
- `Python 3.11+`
- optional virtual environment tooling
- (챗봇) `GOOGLE_API_KEY` 또는 로컬 Ollama 서버

### Install
```bash
git clone https://github.com/sungjin9288/2-sungjin-community-be.git
cd 2-sungjin-community-be
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment
Example local environment (`.env`):

```env
DATABASE_URL=sqlite:///./community.db
CORS_ALLOW_ORIGINS=http://localhost:3001,http://127.0.0.1:3001

# 챗봇 설정
LLM_PROVIDER=gemini          # gemini | ollama | mock
GOOGLE_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.0-flash

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

SHOPS_CSV_PATH=data/shops.csv
LOGS_CSV_PATH=data/logs.csv
```

### Run
```bash
uvicorn app.main:app --reload
```

Production-style local run:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open:
- `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Chatbot quick test
```bash
# 상태 확인
curl http://localhost:8000/chatbot/status

# 식당 추천
curl -X POST http://localhost:8000/chatbot/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "강남 파스타 데이트 맛집 추천해줘"}'

# 비관련 질문 거절 확인
curl -X POST http://localhost:8000/chatbot/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "삼성전자 주가 전망해줘"}'
```

## 테스트 / 검증 | Test & Verification

### Pytest
```bash
pytest -q
```

### Health check
```bash
curl -s http://localhost:8000/health
```

Expected response:
```json
{"status":"healthy","db":"ok"}
```

### Frontend-integrated verification
The paired frontend repository provides higher-level smoke validation via:
- `npm run test:integration`
- `npm run test:upload`

## API Surface Summary | API 요약

| Domain | Endpoints |
| --- | --- |
| Auth | `/auth/signup`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/check-email`, `/auth/check-nickname` |
| Users | `/users/me`, `/users/me/password`, account management routes |
| Posts | post list/detail/create/update/delete, like, bookmark, trending |
| Comments | comment create/list/update/delete (threaded) |
| Messages | `/messages/users`, `/messages/conversations`, `/messages/with/{user_id}`, `/messages` |
| Social | block/unblock, report, notifications |
| Images | image-related upload helpers and mounted static paths |
| **Chatbot** | **`POST /chatbot/chat`, `POST /chatbot/reset`, `GET /chatbot/status`** |

## 배포 자산 | Delivery Assets

### Containerization
- `Dockerfile`
- `.dockerignore`
- `Dockerfile.lambda`

### Deployment Helpers
- `scripts/deploy-lambda-image.sh`
- `scripts/ec2-bluegreen-be-deploy.sh`
- `deploy/ecs/task-definition.template.json`

### Workflow / CI/CD Assets
- `.github/workflows/ci-backend.yml`
- `.github/workflows/deploy-lambda-image.yml`
- `.github/workflows/deploy-ecs-fargate.yml`
- blue/green support assets in the paired frontend repository

## Infra / Delivery Coverage | 수행 범위

This backend participated in validating the following runtime targets together with the frontend repository:

| Target | Status | Notes |
| --- | --- | --- |
| Docker image build | Done | backend image build validated |
| Docker Compose on EC2 | Done | FE/BE combined compose deployment validated |
| ECS Fargate | Done | backend task definition and service rollout validated |
| Lambda container image | Done | image packaging and deployment workflow prepared/validated |
| Kubernetes (staging validation) | Done | backend image deployed to EKS staging during validation |
| Blue/Green deployment support | Done | backend deployment helper assets prepared |

## Portfolio Value | 포트폴리오 관점의 강점
This repository demonstrates:

- API-first backend design
- runtime configurability instead of hardcoded infra coupling
- production-style startup hardening
- health-check-aware deployment readiness
- multi-target packaging strategy (EC2 / ECS / Lambda / K8s)
- cost-aware operations after validation
- **LLM-integrated chatbot with multi-provider support (Gemini / Ollama)**
- **user behavior log-based recommendation ranking at scale (7.1M rows)**

## Cost Control / 비용 정리 원칙
Because this project is a personal portfolio artifact, not a commercial service, the validated cloud runtime resources were removed after verification.

What remains in Git:
- backend source code
- Docker and Lambda packaging assets
- ECS deployment template
- CI/CD workflow definitions
- integration-compatible app structure

## Related Repository & Documents
- Frontend repo: `https://github.com/sungjin9288/2-sungjin-community-fe`
- Frontend infra report: `../2-sungjin-community-fe/docs/community-infra-reliability-report.md`
- Frontend deployment checklist: `../2-sungjin-community-fe/docs/deployment-execution-checklist.md`

## License
This project is released under the `MIT` License unless stated otherwise.
