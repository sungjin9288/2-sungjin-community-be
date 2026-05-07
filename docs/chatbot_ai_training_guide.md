# 식당 추천 AI 학습 가이드

이 프로젝트에서 학습 대상은 LLM 자체가 아니라 **식당 추천 랭킹 모델**입니다. LLM은 대화와 설명을 담당하고, 실제 추천 후보와 순위는 데이터셋 기반 추천 엔진이 결정해야 합니다.

## 1. 데이터 수집

서버 실행 시 학습 로그 경로를 지정합니다.

```bash
CHATBOT_LEARNING_LOG_PATH=data/chatbot_learning_logs.jsonl \
LLM_PROVIDER=mock \
.venv312/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

저장되는 이벤트:

| 이벤트 | 내용 | 용도 |
|---|---|---|
| `chat` | 사용자 질의, 추천 후보, rank, score, score_breakdown, 추천 이유 | 노출 후보와 랭킹 피처 분석 |
| `feedback` | 좋아요/별로예요/저장, 대상 식당, 당시 프로필 | 학습 label 생성 |

## 2. 학습 샘플 생성

수집된 로그를 랭킹 학습용 JSONL로 변환합니다.

```bash
python scripts/export_chatbot_learning_dataset.py \
  --input data/chatbot_learning_logs.jsonl \
  --output data/chatbot_training_samples.jsonl
```

초기에는 추천 카드 피드백이 부족할 수 있습니다. 이때는 기존 행동 로그의 `click/view/bookmark/reservation` 가중치를 query별 relevance label로 사용해 weak-label 학습셋을 먼저 만듭니다.

```bash
python scripts/build_recommendation_training_dataset.py \
  --max-rows 500000 \
  --max-queries 200 \
  --candidate-k 50 \
  --output data/recommendation_training_samples.jsonl
```

이 데이터는 실제 챗봇 피드백이 쌓이기 전의 초기 랭킹 실험용입니다. 운영 피드백이 충분해지면 `data/chatbot_training_samples.jsonl`을 우선 사용하고, 행동 로그 기반 샘플은 보조 검증셋으로 둡니다.

label 규칙:

| 사용자 행동 | label |
|---|---:|
| `like` | `1.0` |
| `save` | `1.0` |
| `dislike` | `0.0` |

샘플 예시:

```json
{
  "query": "강남 데이트 파스타 맛집 추천해줘",
  "shop_id": "shop-1",
  "label": 1.0,
  "features": {
    "rank": 1,
    "score": 0.77,
    "bm25": 0.69,
    "intent": 1.0,
    "popularity": 0.18,
    "personal": 1.0
  }
}
```

## 3. 첫 학습 전략

처음부터 복잡한 딥러닝 모델을 붙이지 말고 아래 순서로 진행합니다.

1. **가중치 튜닝**
   - 현재 공식: `BM25`, `intent_log`, `popularity`, `personal`
   - `data/recommendation_training_samples.jsonl` 또는 `data/chatbot_training_samples.jsonl`에서 positive/negative label을 기준으로 grid search
   - 목표: NDCG@5, MRR@5 개선

   ```bash
   python scripts/tune_chatbot_rank_weights.py \
     --input data/recommendation_training_samples.jsonl \
     --output data/chatbot_rank_weight_report.json \
     --top-k 5 \
     --step 0.1 \
     --min-groups 3
   ```

   결과가 `status: "insufficient_data"`이면 query별 positive/negative 후보가 부족한 상태입니다. 추천 카드의 `좋아요`, `저장`, `별로예요` 피드백을 더 수집한 뒤 다시 실행합니다. 행동 로그 기반 학습셋처럼 `personal` 값이 모두 0인 피처는 튜닝 대상에서 자동 제외됩니다.

2. **Learning-to-Rank 모델**
   - 후보: LightGBM LambdaRank, XGBoost rank:pairwise
   - 입력 피처: `bm25`, `intent`, `popularity`, `personal`, `rank`, `category_count`, `menu_count`
   - 그룹 기준: `query` 또는 `session_id + query`

3. **서빙 적용**
   - 모델 artifact가 있을 때만 ML 재랭킹 적용
   - artifact가 없거나 예측 실패 시 기존 공식 랭킹으로 fallback
   - 추천 결과에는 계속 `score_breakdown`과 `reasons`를 노출

## 4. 평가

기존 로그 기반 평가는 아래 명령으로 유지합니다.

```bash
python scripts/evaluate_recommendation.py \
  --max-rows 100000 \
  --max-queries 20 \
  --top-k 5 \
  --output data/recommendation_eval_report.json \
  --details-output data/recommendation_eval_details.jsonl
```

요약 리포트는 `NDCG@K`, `MRR@K`, `HitRate@K`, `Coverage@K`, `zero_result_rate`, `avg/p50/p95/max latency`를 포함합니다. query별 상세 JSONL에는 추천된 `shop_id`, 정답 후보 수, query별 latency가 저장됩니다.

운영 전 체크리스트:

- `like/save/dislike` 피드백이 최소 수백 건 이상 쌓였는가
- `dislike`가 특정 카테고리에 치우치지 않는가
- 명시 메뉴 질의에서 비관련 카테고리가 상위에 오르지 않는가
- NDCG@5, MRR@5, HitRate@5, Coverage@5, p95 latency를 기존 공식과 비교했는가
- 모델 실패 시 공식 기반 fallback이 동작하는가

## 5. 개인정보 주의

현재 로그는 세션 ID, 질의, 추천 후보, 피드백을 포함합니다. 이메일, 닉네임, 원본 프로필 사진 같은 회원 개인정보는 학습 로그에 넣지 않습니다. 외부 학습 환경으로 옮기기 전에는 `session_id`도 해시 처리하는 것을 권장합니다.
