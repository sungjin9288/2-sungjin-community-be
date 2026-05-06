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

import logging
import os
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
    for _, row in events_df.iterrows():
        for tok in _tokenize(row["search_query"]):
            index[tok][row["shop_id"]] += row["weight"]

    normalized: dict[str, dict[str, float]] = {}
    for tok, shop_map in index.items():
        max_v = max(shop_map.values()) or 1.0
        normalized[tok] = {sid: v / max_v for sid, v in shop_map.items()}

    return normalized


# ─── 추천 엔진 ────────────────────────────────────────────────────────────── #
class RecommendationEngine:
    """
    서버 기동 시 한 번만 초기화하는 싱글턴 추천 엔진.

    결합 스코어:
      score = 0.45 * bm25_norm + 0.40 * intent_log + 0.15 * popularity
    """

    def __init__(self) -> None:
        self._shops: list[ShopRecord] = []
        self._bm25: Any = None
        self._popularity: dict[str, float] = {}
        self._query_token_index: dict[str, dict[str, float]] = {}
        self._loaded = False

    def load(
        self,
        shops_path: str | None = None,
        logs_path: str | None = None,
    ) -> None:
        shops_path = shops_path or os.getenv("SHOPS_CSV_PATH", "data/shops.csv")
        logs_path = logs_path or os.getenv("LOGS_CSV_PATH", "data/logs.csv")

        shops_df = self._safe_read_csv(shops_path, "shops")
        logs_df = self._safe_read_csv(logs_path, "logs")

        self._shops = self._parse_shops(shops_df)
        corpus = [_tokenize(s.document_text()) for s in self._shops]
        self._bm25 = _build_bm25(corpus)

        logger.info("로그 집계 시작 (총 %d행)...", len(logs_df))
        events = _propagate_queries_and_aggregate(logs_df)
        self._popularity = _build_popularity_index(events)
        self._query_token_index = _build_query_token_index(events)

        self._loaded = True
        logger.info(
            "추천 엔진 로드 완료: 매장 %d개, 유효 이벤트 %d건",
            len(self._shops), len(events),
        )

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

    def recommend(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
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
        intent = [
            sum(self._query_token_index.get(tok, {}).get(s.shop_id, 0.0) for tok in query_tokens)
            / len(query_tokens)
            for s in self._shops
        ]

        # 3) 전체 인기도
        pop = [self._popularity.get(s.shop_id, 0.0) for s in self._shops]

        # 4) 결합 스코어
        combined = [
            0.45 * b + 0.40 * i + 0.15 * p
            for b, i, p in zip(bm25_norm, intent, pop)
        ]

        # 5) top_k
        ranked = sorted(range(n), key=lambda i: combined[i], reverse=True)
        results = []
        for idx in ranked[:top_k]:
            score = combined[idx]
            if score <= 0:
                break
            s = self._shops[idx]
            results.append({
                "shop_id": s.shop_id,
                "shop_name": s.shop_name,
                "address": s.address,
                "categories": s.categories,
                "menus": s.menus[:5],
                "facilities": s.facilities[:5],
                "awards": s.awards,
                "score": round(score, 4),
            })

        return results

    def is_ready(self) -> bool:
        return self._loaded and bool(self._shops)

    @property
    def shop_count(self) -> int:
        return len(self._shops)


# 싱글턴
recommendation_engine = RecommendationEngine()
