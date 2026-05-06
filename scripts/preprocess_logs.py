"""
scripts/preprocess_logs.py

710만 행 logs.csv를 사전에 집계하여 pkl 캐시를 생성한다.
서버 기동 시 pkl이 있으면 바로 로드하므로 시작 시간이 크게 단축된다.

사용법:
    python scripts/preprocess_logs.py
    # → data/log_cache.pkl 생성

    # 강제 재생성:
    python scripts/preprocess_logs.py --force
"""

from __future__ import annotations

import argparse
import logging
import pickle
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="로그 사전 집계 스크립트")
    parser.add_argument(
        "--logs", default="data/logs.csv", help="logs.csv 경로 (기본값: data/logs.csv)"
    )
    parser.add_argument(
        "--out", default="data/log_cache.pkl", help="출력 pkl 경로 (기본값: data/log_cache.pkl)"
    )
    parser.add_argument("--force", action="store_true", help="캐시가 있어도 강제 재생성")
    args = parser.parse_args()

    out_path = Path(args.out)

    if out_path.exists() and not args.force:
        logger.info("캐시 파일 이미 존재: %s (--force 로 재생성 가능)", out_path)
        return

    # 늦게 import (서버 기동 없이도 실행 가능하도록)
    try:
        import pandas as pd
    except ImportError:
        logger.error("pandas 미설치: pip install pandas")
        sys.exit(1)

    # recommendation_engine 모듈에서 집계 함수 가져오기
    try:
        from app.chatbot.recommendation_engine import (
            LOG_CACHE_VERSION,
            _build_popularity_index,
            _build_query_phrase_index,
            _build_query_token_index,
            _propagate_queries_and_aggregate,
        )
    except ImportError as e:
        logger.error("app 모듈을 찾을 수 없습니다. 경로를 확인해주세요. %s", e)
        sys.exit(1)

    logs_path = Path(args.logs)
    if not logs_path.exists():
        logger.error("logs.csv 없음: %s", logs_path)
        sys.exit(1)

    logger.info("logs.csv 로드 중: %s", logs_path)
    t0 = time.time()
    logs_df = pd.read_csv(logs_path, encoding="utf-8-sig")
    logger.info("로드 완료: %d행 (%.1fs)", len(logs_df), time.time() - t0)

    logger.info("이벤트 집계 시작...")
    t1 = time.time()
    events = _propagate_queries_and_aggregate(logs_df)
    logger.info("집계 완료: %d건 (%.1fs)", len(events), time.time() - t1)

    logger.info("인기도 인덱스 빌드 중...")
    t2 = time.time()
    popularity = _build_popularity_index(events)
    logger.info("인기도 완료: %d개 매장 (%.1fs)", len(popularity), time.time() - t2)

    logger.info("query 토큰 인덱스 빌드 중...")
    t3 = time.time()
    query_token_index = _build_query_token_index(events)
    logger.info("토큰 인덱스 완료: %d개 토큰 (%.1fs)", len(query_token_index), time.time() - t3)

    logger.info("query phrase 인덱스 빌드 중...")
    t4 = time.time()
    query_phrase_index = _build_query_phrase_index(events)
    logger.info("phrase 인덱스 완료: %d개 query (%.1fs)", len(query_phrase_index), time.time() - t4)

    cache = {
        "version": LOG_CACHE_VERSION,
        "source": {
            "logs": str(logs_path),
            "rows": int(len(logs_df)),
            "events": int(len(events)),
        },
        "popularity": popularity,
        "query_token_index": query_token_index,
        "query_phrase_index": query_phrase_index,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)

    logger.info(
        "캐시 저장 완료: %s (%.1f KB)",
        out_path,
        out_path.stat().st_size / 1024,
    )
    logger.info("총 소요 시간: %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
