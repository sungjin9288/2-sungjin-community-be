"""
recommendation_engine.py

BM25 기반 식당 검색 + 사용자 행동 로그 기반 랭킹 엔진.

실제 데이터 스키마:
  shops.csv  : shop_id, shop_name, address, menus, categories, facilities, awards
  logs.csv   : event_type, event_timestamp, user_id, session_id, shop_id, search_query, position

설계 원칙:
  - 서버 기동 시 CSV를 한 번만 로드하여 메모리에 인덱스 구축 (cold-path 제거)
  - pandas 벡터 연산으로 710만 행 로그 고속 처리 (iterrows 미사용)
  - 세션 기반 ffill로 bookmark/reservation에 search_query 역전파
  - 의도 스코어(log)로 후식라면 오마카세 등 BM25 오매칭 보정
"""

from __future__ import annotations

import json
import logging
import os
import pickle
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ─── 이벤트 가중치 ────────────────────────────────────────────────────────── #
EVENT_WEIGHTS: dict[str, float] = {
    "impression": 0.0,
    "click": 1.0,
    "view": 2.0,
    "bookmark": 5.0,
    "reservation": 10.0,
}
DEFAULT_TOP_K = 5
LOG_CACHE_VERSION = 2
RANK_WEIGHT_ARTIFACT_ENV = "CHATBOT_RANK_WEIGHT_PATH"
DEFAULT_RANK_WEIGHT_ARTIFACT_PATH = "data/chatbot_rank_weight_report.json"
RANK_WEIGHT_FEATURES = ("bm25", "intent", "popularity", "personal")
DEFAULT_BASE_RANK_WEIGHTS: dict[str, float] = {
    "bm25": 0.45,
    "intent": 0.40,
    "popularity": 0.15,
    "personal": 0.0,
}
DEFAULT_PERSONAL_RANK_WEIGHTS: dict[str, float] = {
    "bm25": 0.35,
    "intent": 0.30,
    "popularity": 0.15,
    "personal": 0.20,
}
CUISINE_ALIASES: dict[str, tuple[str, ...]] = {
    "파스타": ("파스타", "이탈리아", "이탈리안"),
    "이탈리아": ("이탈리아", "이탈리안", "파스타", "피자"),
    "고기": ("고기", "소고기", "돼지고기", "삼겹살", "갈비", "스테이크", "바비큐", "육류"),
    "평냉": ("평냉", "냉면", "평양냉면"),
    "냉면": ("냉면", "평냉", "평양냉면"),
    "라면": ("라면", "라멘"),
    "라멘": ("라멘", "라면"),
    "스시": ("스시", "초밥", "일식"),
    "초밥": ("초밥", "스시", "일식"),
    "카페": ("카페", "커피", "디저트", "브런치", "베이커리"),
}

# ─── 형태소 분석 (kiwipiepy 우선, fallback: 공백 분리) ────────────────────── #
try:
    from kiwipiepy import Kiwi

    _kiwi = Kiwi()

    def _tokenize(text: str) -> list[str]:
        """한국어 형태소 분석. 명사·외래어 중심 추출."""
        if not text or not text.strip():
            return []
        result = _kiwi.analyze(text)
        tokens = [
            t.form.lower()
            for t in result[0][0]
            if t.tag in ("NNG", "NNP", "SL", "SH", "XR")
        ]
        return tokens if tokens else text.lower().split()

    logger.info("kiwipiepy 형태소 분석기 로드 완료")

except Exception:
    logger.warning("kiwipiepy 없음 — 공백 split fallback 사용")

    def _tokenize(text: str) -> list[str]:  # type: ignore[misc]
        return text.lower().split() if text else []


# ─── BM25 (rank_bm25 우선, fallback: TF 기반) ────────────────────────────── #
try:
    from rank_bm25 import BM25Okapi as _BM25Lib

    def _build_bm25(corpus: list[list[str]]):
        return _BM25Lib(corpus, k1=1.5, b=0.75)

    def _bm25_scores(bm25, query_tokens: list[str]) -> list[float]:
        return bm25.get_scores(query_tokens).tolist()

    logger.info("rank_bm25 로드 완료")

except Exception:
    logger.warning("rank_bm25 없음 — TF 기반 fallback 사용")

    def _build_bm25(corpus: list[list[str]]):  # type: ignore[misc]
        return corpus

    def _bm25_scores(corpus, query_tokens: list[str]) -> list[float]:  # type: ignore[misc]
        q = set(query_tokens)
        return [float(len(q & set(doc))) for doc in corpus]


# ─── 데이터 클래스 ────────────────────────────────────────────────────────── #
@dataclass
class ShopRecord:
    shop_id: str
    shop_name: str
    address: str
    categories: list[str]
    menus: list[str]
    facilities: list[str]
    awards: list[str]
    raw: dict[str, Any] = field(default_factory=dict)

    def document_text(self) -> str:
        """BM25 인덱싱 텍스트. categories·shop_name 핵심, menus는 보조."""
        parts = [
            self.shop_name,
            self.address,
            " ".join(self.categories),
            " ".join(self.facilities),
            " ".join(self.menus),
            " ".join(self.awards),
        ]
        return " ".join(p for p in parts if p)


# ─── 로그 집계 ────────────────────────────────────────────────────────────── #
def _propagate_queries_and_aggregate(logs_df: pd.DataFrame) -> pd.DataFrame:
    """
    pandas 벡터 연산으로 세션 내 search_query를 forward-fill하여
    bookmark/reservation 이벤트에 전파한다 (710만 행 고속 처리).
    """
    if logs_df.empty:
        return pd.DataFrame(columns=["shop_id", "search_query", "event_type", "weight"])

    df = logs_df.copy()
    df["event_timestamp"] = pd.to_numeric(df["event_timestamp"], errors="coerce")
    df["search_query"] = df["search_query"].fillna("").astype(str).str.strip()
    df["event_type"] = df["event_type"].str.strip().str.lower()
    df["shop_id"] = df["shop_id"].astype(str).str.strip()

    # 시간순 정렬 후 세션 내 query forward-fill
    df = df.sort_values(["session_id", "event_timestamp"]).reset_index(drop=True)
    df["search_query"] = df["search_query"].replace("", pd.NA)
    df["search_query"] = df.groupby("session_id")["search_query"].ffill().fillna("")

    # 이벤트 가중치 부여
    weight_map = pd.Series(EVENT_WEIGHTS)
    df["weight"] = df["event_type"].map(weight_map).fillna(0.0)

    # 유효 이벤트 필터링
    mask = (df["weight"] > 0) & (df["search_query"] != "") & (df["shop_id"] != "nan")
    return df.loc[mask, ["shop_id", "search_query", "event_type", "weight"]].reset_index(drop=True)


def _normalize_query(text: str) -> str:
    """query 비교용 정규화 key. 형태소 토큰이 있으면 토큰열을 기준으로 한다."""
    tokens = _tokenize(str(text or ""))
    return " ".join(tokens).strip()


def _build_popularity_index(events_df: pd.DataFrame) -> dict[str, float]:
    """shop_id → 인기도 (0~1 정규화)."""
    if events_df.empty:
        return {}
    pop = events_df.groupby("shop_id")["weight"].sum()
    return (pop / (pop.max() or 1.0)).to_dict()


def _build_query_token_index(events_df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """
    query 토큰 → { shop_id: 정규화 가중치 합 }.

    라면 맛집 의도 보정:
    - 오마카세 후식라면 매장은 '라면' query log에서 클릭·예약이 거의 없음
    - 따라서 intent 스코어가 낮게 형성되어 결합 점수에서 자동 하위 랭크
    """
    if events_df.empty:
        return {}

    index: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    grouped = events_df.groupby(["search_query", "shop_id"], as_index=False)["weight"].sum()
    for row in grouped.itertuples(index=False):
        for tok in _tokenize(row.search_query):
            index[tok][row.shop_id] += row.weight

    normalized: dict[str, dict[str, float]] = {}
    for tok, shop_map in index.items():
        max_v = max(shop_map.values()) or 1.0
        normalized[tok] = {sid: v / max_v for sid, v in shop_map.items()}

    return normalized


def _build_query_phrase_index(events_df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """
    정규화된 전체 query/부분 phrase → { shop_id: 정규화 가중치 합 }.

    토큰 단독 합산은 "성수 인기"와 "데이트 인기"를 섞을 수 있으므로,
    실제 검색 로그에 같이 등장한 phrase를 별도 신호로 둔다.
    """
    if events_df.empty:
        return {}

    df = events_df.copy()
    df["query_key"] = df["search_query"].map(_normalize_query)
    df = df[df["query_key"] != ""]
    if df.empty:
        return {}

    grouped = df.groupby(["query_key", "shop_id"], as_index=False)["weight"].sum()
    index: dict[str, dict[str, float]] = {}
    for query_key, group in grouped.groupby("query_key"):
        shop_map = dict(zip(group["shop_id"], group["weight"], strict=False))
        max_v = max(shop_map.values()) or 1.0
        index[query_key] = {sid: v / max_v for sid, v in shop_map.items()}
    return index


def _query_phrase_keys(tokens: list[str]) -> list[str]:
    """입력 query 토큰에서 full phrase와 2~3gram 후보를 만든다."""
    if len(tokens) < 2:
        return []

    keys: list[str] = [" ".join(tokens)]
    max_size = min(3, len(tokens))
    for size in range(max_size, 1, -1):
        for start in range(0, len(tokens) - size + 1):
            key = " ".join(tokens[start:start + size])
            if key not in keys:
                keys.append(key)
    return keys


# ─── 추천 엔진 ────────────────────────────────────────────────────────────── #
class RecommendationEngine:
    """
    서버 기동 시 한 번만 초기화하는 싱글턴 추천 엔진.

    결합 스코어:
      기본 score = 0.45 * bm25_norm + 0.40 * intent_log + 0.15 * popularity
      개인화 score = 0.35 * bm25_norm + 0.30 * intent_log + 0.15 * popularity + 0.20 * preference
    """

    def __init__(self) -> None:
        self._shops: list[ShopRecord] = []
        self._bm25: Any = None
        self._popularity: dict[str, float] = {}
        self._query_token_index: dict[str, dict[str, float]] = {}
        self._query_phrase_index: dict[str, dict[str, float]] = {}
        self._base_rank_weights = DEFAULT_BASE_RANK_WEIGHTS.copy()
        self._personal_rank_weights = DEFAULT_PERSONAL_RANK_WEIGHTS.copy()
        self._rank_weight_source = "default"
        self._rank_weight_metadata: dict[str, Any] = {}
        self._reset_rank_weights()
        self._loaded = False

    def load(
        self,
        shops_path: str | None = None,
        logs_path: str | None = None,
    ) -> None:
        shops_path = shops_path or os.getenv("SHOPS_CSV_PATH", "data/shops.csv")
        logs_path = logs_path or os.getenv("LOGS_CSV_PATH", "data/logs.csv")
        cache_path = os.getenv("LOG_CACHE_PATH", "data/log_cache.pkl")
        rank_weight_path = os.getenv(RANK_WEIGHT_ARTIFACT_ENV, DEFAULT_RANK_WEIGHT_ARTIFACT_PATH)
        self._load_rank_weight_artifact(rank_weight_path)

        shops_df = self._safe_read_csv(shops_path, "shops")

        self._shops = self._parse_shops(shops_df)
        corpus = [_tokenize(s.document_text()) for s in self._shops]
        self._bm25 = _build_bm25(corpus or [["__empty__"]])

        if self._load_log_cache(cache_path):
            self._loaded = True
            logger.info(
                "추천 엔진 로드 완료: 매장 %d개, 로그 캐시 사용",
                len(self._shops),
            )
            return

        logs_df = self._safe_read_csv(logs_path, "logs")
        logger.info("로그 집계 시작 (총 %d행)...", len(logs_df))
        events = _propagate_queries_and_aggregate(logs_df)
        self._build_log_indexes(events)

        self._loaded = True
        logger.info(
            "추천 엔진 로드 완료: 매장 %d개, 유효 이벤트 %d건",
            len(self._shops), len(events),
        )

    def _build_log_indexes(self, events: pd.DataFrame) -> None:
        self._popularity = _build_popularity_index(events)
        self._query_token_index = _build_query_token_index(events)
        self._query_phrase_index = _build_query_phrase_index(events)

    @staticmethod
    def _safe_weight(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        if pd.isna(number) or number < 0:
            return 0.0
        return number

    @classmethod
    def _normalise_rank_weights(
        cls,
        weights: dict[str, Any],
        active_features: tuple[str, ...],
        fallback: dict[str, float],
    ) -> dict[str, float]:
        cleaned = {
            feature: cls._safe_weight(weights.get(feature))
            for feature in RANK_WEIGHT_FEATURES
        }
        total = sum(cleaned[feature] for feature in active_features)
        if total <= 0:
            return fallback.copy()
        return {
            feature: round(cleaned[feature] / total, 6) if feature in active_features else 0.0
            for feature in RANK_WEIGHT_FEATURES
        }

    @staticmethod
    def _format_rank_formula(weights: dict[str, float]) -> str:
        labels = {
            "bm25": "search_match",
            "intent": "intent_log",
            "popularity": "popularity",
            "personal": "personal_preference",
        }
        parts = [
            f"{weights.get(feature, 0.0):.2f}*{labels[feature]}"
            for feature in RANK_WEIGHT_FEATURES
            if weights.get(feature, 0.0) > 0
        ]
        return " + ".join(parts) or "0"

    @staticmethod
    def _score_contributions(
        weights: dict[str, float],
        score_breakdown: dict[str, float],
    ) -> dict[str, float]:
        """Return each ranking signal's weighted contribution before filters."""
        return {
            feature: round(weights.get(feature, 0.0) * score_breakdown.get(feature, 0.0), 4)
            for feature in RANK_WEIGHT_FEATURES
            if weights.get(feature, 0.0) > 0
        }

    def _reset_rank_weights(self) -> None:
        self._base_rank_weights = DEFAULT_BASE_RANK_WEIGHTS.copy()
        self._personal_rank_weights = DEFAULT_PERSONAL_RANK_WEIGHTS.copy()
        self._rank_weight_source = "default"
        self._rank_weight_metadata = {
            "status": "default",
            "source": "default",
            "active_features": [],
            "base_weights": self._base_rank_weights.copy(),
            "personal_weights": self._personal_rank_weights.copy(),
        }

    def _apply_rank_weights(
        self,
        weights: dict[str, Any],
        *,
        active_features: list[str] | tuple[str, ...] | None = None,
        source: str,
    ) -> bool:
        active = tuple(
            feature
            for feature in (active_features or [])
            if feature in RANK_WEIGHT_FEATURES
        )
        if not active:
            active = tuple(
                feature
                for feature in RANK_WEIGHT_FEATURES
                if self._safe_weight(weights.get(feature)) > 0
            )
        if not active:
            return False

        base_features = tuple(feature for feature in active if feature != "personal")
        self._base_rank_weights = self._normalise_rank_weights(
            weights,
            base_features,
            DEFAULT_BASE_RANK_WEIGHTS,
        )

        if "personal" in active:
            self._personal_rank_weights = self._normalise_rank_weights(
                weights,
                active,
                DEFAULT_PERSONAL_RANK_WEIGHTS,
            )
        else:
            personal_budget = DEFAULT_PERSONAL_RANK_WEIGHTS["personal"]
            non_personal = self._normalise_rank_weights(
                weights,
                base_features,
                DEFAULT_BASE_RANK_WEIGHTS,
            )
            self._personal_rank_weights = {
                feature: round(non_personal[feature] * (1.0 - personal_budget), 6)
                for feature in RANK_WEIGHT_FEATURES
            }
            self._personal_rank_weights["personal"] = personal_budget

        self._rank_weight_source = source
        self._rank_weight_metadata = {
            "status": "applied",
            "source": source,
            "active_features": list(active),
            "base_weights": self._base_rank_weights.copy(),
            "personal_weights": self._personal_rank_weights.copy(),
        }
        return True

    def _load_rank_weight_artifact(self, path: str) -> bool:
        self._reset_rank_weights()
        if not path:
            return False

        p = Path(path)
        if not p.exists():
            logger.info("랭킹 가중치 artifact 없음: %s", path)
            return False

        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("랭킹 가중치 artifact 로드 실패, 기본값 사용: %s", exc)
            return False

        if not isinstance(payload, dict) or payload.get("status") != "ok":
            logger.warning("랭킹 가중치 artifact 비활성 상태, 기본값 사용: %s", path)
            return False

        weights = payload.get("best_weights")
        if not isinstance(weights, dict):
            logger.warning("랭킹 가중치 artifact best_weights 없음, 기본값 사용: %s", path)
            return False

        active_features = payload.get("active_features")
        if not isinstance(active_features, list):
            active_features = []

        applied = self._apply_rank_weights(
            weights,
            active_features=active_features,
            source=str(p),
        )
        if applied:
            self._rank_weight_metadata.update({
                "status": "artifact",
                "source": str(p),
                "top_k": payload.get("top_k"),
                "samples": payload.get("samples"),
                "eligible_groups": payload.get("eligible_groups"),
                "baseline_metrics": payload.get("baseline_metrics") or {},
                "best_metrics": payload.get("best_metrics") or {},
                "best_weights": payload.get("best_weights") or {},
                "promotion": payload.get("promotion") if isinstance(payload.get("promotion"), dict) else {},
            })
            logger.info(
                "랭킹 가중치 artifact 적용: %s (base=%s, personal=%s)",
                path,
                self._base_rank_weights,
                self._personal_rank_weights,
            )
        else:
            logger.warning("랭킹 가중치 artifact 적용 실패, 기본값 사용: %s", path)
        return applied

    def _load_log_cache(self, path: str) -> bool:
        p = Path(path)
        if not p.exists():
            logger.info("로그 캐시 없음: %s", path)
            return False
        try:
            with open(p, "rb") as f:
                cache = pickle.load(f)
        except Exception as exc:
            logger.warning("로그 캐시 로드 실패, CSV 집계로 전환: %s", exc)
            return False

        if not isinstance(cache, dict):
            logger.warning("로그 캐시 형식 오류, CSV 집계로 전환: %s", path)
            return False

        self._popularity = cache.get("popularity") or {}
        self._query_token_index = cache.get("query_token_index") or {}
        self._query_phrase_index = cache.get("query_phrase_index") or {}
        version = cache.get("version")
        if version != LOG_CACHE_VERSION:
            logger.warning(
                "로그 캐시 버전 불일치(version=%s, expected=%s). 재생성 권장: python scripts/preprocess_logs.py --force",
                version,
                LOG_CACHE_VERSION,
            )

        logger.info(
            "로그 캐시 로드 완료: popularity=%d, token_index=%d, phrase_index=%d",
            len(self._popularity),
            len(self._query_token_index),
            len(self._query_phrase_index),
        )
        return bool(self._popularity or self._query_token_index)

    @staticmethod
    def _safe_read_csv(path: str, label: str) -> pd.DataFrame:
        p = Path(path)
        if not p.exists():
            logger.warning("[%s] CSV 없음: %s", label, path)
            return pd.DataFrame()
        try:
            return pd.read_csv(p, encoding="utf-8-sig")
        except Exception as exc:
            logger.error("[%s] CSV 읽기 실패: %s", label, exc)
            return pd.DataFrame()

    @staticmethod
    def _parse_list_field(val: Any) -> list[str]:
        """콤마 구분 문자열 → 리스트 (NaN·멀티라인 처리)."""
        if pd.isna(val) or not val:
            return []
        raw = str(val).replace("\n", " ").replace("\r", " ").strip()
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _parse_shops(self, df: pd.DataFrame) -> list[ShopRecord]:
        if df.empty:
            return []
        shops = []
        for _, row in df.iterrows():
            shops.append(ShopRecord(
                shop_id=str(row.get("shop_id", "")).strip(),
                shop_name=str(row.get("shop_name", "") or "").strip(),
                address=str(row.get("address", "") or "").strip(),
                categories=self._parse_list_field(row.get("categories")),
                menus=self._parse_list_field(row.get("menus")),
                facilities=self._parse_list_field(row.get("facilities")),
                awards=self._parse_list_field(row.get("awards")),
                raw=row.to_dict(),
            ))
        return shops

    @staticmethod
    def _shop_text(shop: ShopRecord) -> str:
        return " ".join([
            shop.shop_name,
            shop.address,
            " ".join(shop.categories),
            " ".join(shop.menus),
            " ".join(shop.facilities),
            " ".join(shop.awards),
        ]).lower()

    @staticmethod
    def _list_profile(profile: dict[str, Any] | None, key: str) -> list[str]:
        if not isinstance(profile, dict):
            return []
        values = profile.get(key) or []
        if isinstance(values, str):
            return [values]
        return [str(value) for value in values if str(value or "").strip()] if isinstance(values, list) else []

    @staticmethod
    def _matches_cuisine(text: str, cuisine: str) -> bool:
        aliases = CUISINE_ALIASES.get(cuisine, (cuisine,))
        return any(alias.lower() in text for alias in aliases)

    def _personal_score(
        self,
        shop: ShopRecord,
        profile: dict[str, Any] | None,
        feedback: dict[str, str] | None,
    ) -> tuple[float, list[str]]:
        if not profile and not feedback:
            return 0.0, []

        text = self._shop_text(shop)
        score = 0.0
        reasons: list[str] = []

        regions = self._list_profile(profile, "regions")
        matched_regions = [region for region in regions if region.lower() in text]
        if matched_regions:
            score += 0.35
            reasons.append(f"선호 지역({matched_regions[0]})과 맞음")

        cuisines = self._list_profile(profile, "cuisines") + self._list_profile(profile, "liked_categories")
        matched_cuisines = [cuisine for cuisine in cuisines if cuisine.lower() in text]
        if matched_cuisines:
            score += 0.35
            reasons.append(f"선호 메뉴/카테고리({matched_cuisines[0]})와 맞음")

        situations = self._list_profile(profile, "situations")
        matched_situations = [situation for situation in situations if situation.lower() in text]
        if matched_situations:
            score += 0.15
            reasons.append(f"선호 상황({matched_situations[0]})에 적합")

        budget = str((profile or {}).get("budget") or "")
        if budget == "가성비":
            score += 0.05
            reasons.append("가성비 조건을 반영")
        elif budget in {"프리미엄", "비싸도 됨"} and any(word in text for word in ("파인다이닝", "코스", "오마카세")):
            score += 0.15
            reasons.append("프리미엄/코스 허용 조건을 반영")

        avoided = self._list_profile(profile, "avoid") + self._list_profile(profile, "disliked_categories")
        if any(word.lower() in text for word in avoided):
            score -= 0.4
            reasons.append("회피 조건과 일부 겹침")

        feedback = feedback or {}
        if feedback.get(shop.shop_id) in {"like", "save"}:
            score += 0.5
            reasons.append("이전에 긍정 피드백한 매장")
        elif feedback.get(shop.shop_id) == "dislike":
            score -= 0.8
            reasons.append("이전에 별로라고 표시한 매장")

        return max(0.0, min(score, 1.0)), reasons

    @staticmethod
    def _score_reasons(
        bm25_score: float,
        intent_score: float,
        popularity_score: float,
        personal_reasons: list[str],
    ) -> list[str]:
        reasons: list[str] = []
        if bm25_score >= 0.45:
            reasons.append("검색어와 매장 정보가 잘 맞음")
        if intent_score >= 0.25:
            reasons.append("비슷한 검색에서 실제 반응이 좋음")
        if popularity_score >= 0.35:
            reasons.append("전체 행동 로그 인기도가 높음")
        reasons.extend(personal_reasons[:2])
        return reasons[:4] or ["검색 조건과 기본 매장 정보가 매칭됨"]

    def _diversified_indices(
        self,
        ranked: list[int],
        combined: list[float],
        top_k: int,
        pool_size: int,
    ) -> list[int]:
        selected: list[int] = []
        used_categories: dict[str, int] = {}
        used_districts: dict[str, int] = {}

        for idx in ranked[:pool_size]:
            shop = self._shops[idx]
            main_category = shop.categories[0] if shop.categories else ""
            district = ""
            parts = shop.address.split()
            if len(parts) >= 2:
                district = parts[1]

            category_count = used_categories.get(main_category, 0)
            district_count = used_districts.get(district, 0)
            if len(selected) >= 2 and category_count >= 2 and district_count >= 3:
                continue

            selected.append(idx)
            if main_category:
                used_categories[main_category] = category_count + 1
            if district:
                used_districts[district] = district_count + 1
            if len(selected) >= top_k:
                break

        if len(selected) < top_k:
            for idx in ranked:
                if idx not in selected and combined[idx] > 0:
                    selected.append(idx)
                if len(selected) >= top_k:
                    break
        return selected

    def recommend(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        profile: dict[str, Any] | None = None,
        feedback: dict[str, str] | None = None,
        diversify: bool = True,
    ) -> list[dict]:
        """query로 매장을 추천한다. 결합 스코어 기반 top_k 반환."""
        if not self._loaded or not self._shops:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        n = len(self._shops)

        # 1) BM25 정규화
        bm25_raw = _bm25_scores(self._bm25, query_tokens)
        bm25_max = max(bm25_raw) or 1.0
        bm25_norm = [s / bm25_max for s in bm25_raw]

        # 2) 행동 로그 의도 스코어
        token_intent = [
            sum(self._query_token_index.get(tok, {}).get(s.shop_id, 0.0) for tok in query_tokens)
            / len(query_tokens)
            for s in self._shops
        ]

        phrase_keys = _query_phrase_keys(query_tokens)
        phrase_maps = [
            self._query_phrase_index[key]
            for key in phrase_keys
            if key in self._query_phrase_index
        ]
        phrase_intent = [
            max((phrase_map.get(s.shop_id, 0.0) for phrase_map in phrase_maps), default=0.0)
            for s in self._shops
        ]

        intent = [
            max(phrase_score, token_score * 0.75)
            for phrase_score, token_score in zip(phrase_intent, token_intent)
        ]

        # 3) 전체 인기도
        pop = [self._popularity.get(s.shop_id, 0.0) for s in self._shops]

        # 4) 개인화 점수
        personal_parts = [
            self._personal_score(s, profile, feedback)
            for s in self._shops
        ]
        personal = [score for score, _ in personal_parts]
        has_personal_context = any(personal) or bool(feedback)
        explicit_regions = [
            region
            for region in self._list_profile(profile, "regions")
            if region and region in str(query)
        ]
        explicit_cuisines = [
            cuisine
            for cuisine in self._list_profile(profile, "cuisines")
            if cuisine and cuisine in str(query)
        ]

        # 5) 결합 스코어
        weights = self._personal_rank_weights if has_personal_context else self._base_rank_weights
        ranking_formula = self._format_rank_formula(weights)
        combined = [
            weights["bm25"] * b
            + weights["intent"] * i
            + weights["popularity"] * p
            + weights["personal"] * ps
            for b, i, p, ps in zip(bm25_norm, intent, pop, personal)
        ]
        region_factors: list[float] | None = None
        region_matches: list[bool] | None = None
        cuisine_factors: list[float] | None = None
        cuisine_matches: list[bool] | None = None

        if explicit_regions:
            region_matches = [
                any(region.lower() in self._shop_text(shop) for region in explicit_regions)
                for shop in self._shops
            ]
            if not any(region_matches):
                logger.info("명시 지역에 맞는 매장 없음: %s", ", ".join(explicit_regions))
                return []
            region_factors = [1.0 if matched else 0.15 for matched in region_matches]
            combined = [
                score * region_factors[idx]
                for idx, score in enumerate(combined)
            ]

        if explicit_cuisines:
            cuisine_matches = [
                any(self._matches_cuisine(self._shop_text(shop), cuisine) for cuisine in explicit_cuisines)
                for shop in self._shops
            ]
            matched_count = sum(1 for matched in cuisine_matches if matched)
            if matched_count == 0:
                logger.info("명시 메뉴에 맞는 매장 없음: %s", ", ".join(explicit_cuisines))
                return []
            penalty = 0.0 if matched_count >= top_k else 0.2
            cuisine_factors = [1.0 if matched else penalty for matched in cuisine_matches]
            combined = [
                score * cuisine_factors[idx]
                for idx, score in enumerate(combined)
            ]

        # 6) top_k + 다양화
        ranked = sorted(range(n), key=lambda i: combined[i], reverse=True)
        selected = (
            self._diversified_indices(ranked, combined, top_k, max(top_k * 8, 20))
            if diversify
            else ranked[:top_k]
        )
        results = []
        for rank, idx in enumerate(selected, start=1):
            score = combined[idx]
            if score <= 0:
                break
            s = self._shops[idx]
            personal_reasons = personal_parts[idx][1]
            score_breakdown = {
                "bm25": round(bm25_norm[idx], 4),
                "intent": round(intent[idx], 4),
                "popularity": round(pop[idx], 4),
                "personal": round(personal[idx], 4),
            }
            score_contributions = self._score_contributions(weights, score_breakdown)
            score_adjustments = []
            if region_factors is not None and region_matches is not None:
                score_adjustments.append({
                    "type": "region_filter",
                    "values": explicit_regions,
                    "matched": region_matches[idx],
                    "factor": region_factors[idx],
                })
            if cuisine_factors is not None and cuisine_matches is not None:
                score_adjustments.append({
                    "type": "cuisine_filter",
                    "values": explicit_cuisines,
                    "matched": cuisine_matches[idx],
                    "factor": cuisine_factors[idx],
                })
            results.append({
                "rank": rank,
                "shop_id": s.shop_id,
                "shop_name": s.shop_name,
                "address": s.address,
                "categories": s.categories,
                "menus": s.menus[:5],
                "facilities": s.facilities[:5],
                "awards": s.awards,
                "score": round(score, 4),
                "score_breakdown": score_breakdown,
                "score_contributions": score_contributions,
                "score_before_adjustments": round(sum(score_contributions.values()), 4),
                "score_adjustments": score_adjustments,
                "ranking_formula": ranking_formula,
                "ranking_weight_source": self._rank_weight_source,
                "reasons": self._score_reasons(
                    bm25_norm[idx],
                    intent[idx],
                    pop[idx],
                    personal_reasons,
                ),
            })

        return results

    def is_ready(self) -> bool:
        return self._loaded and bool(self._shops)

    @property
    def shop_count(self) -> int:
        return len(self._shops)

    @property
    def rank_weight_source(self) -> str:
        return self._rank_weight_source

    @property
    def rank_weight_info(self) -> dict[str, Any]:
        return {
            "status": self._rank_weight_metadata.get("status", "default"),
            "source": self._rank_weight_source,
            "active_features": list(self._rank_weight_metadata.get("active_features") or []),
            "base_weights": self._base_rank_weights.copy(),
            "personal_weights": self._personal_rank_weights.copy(),
            "top_k": self._rank_weight_metadata.get("top_k"),
            "samples": self._rank_weight_metadata.get("samples"),
            "eligible_groups": self._rank_weight_metadata.get("eligible_groups"),
            "baseline_metrics": dict(self._rank_weight_metadata.get("baseline_metrics") or {}),
            "best_metrics": dict(self._rank_weight_metadata.get("best_metrics") or {}),
            "best_weights": dict(self._rank_weight_metadata.get("best_weights") or {}),
            "promotion": dict(self._rank_weight_metadata.get("promotion") or {}),
        }


# 싱글턴
recommendation_engine = RecommendationEngine()
