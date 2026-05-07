"""
personalization.py

식당 추천 챗봇의 세션별 취향 프로필과 피드백을 관리한다.

LocalStorage payload + 서버 세션 상태를 병합하고, 기본적으로 DB에 장기 저장한다.
CHATBOT_MEMORY_BACKEND=memory 로 설정하면 DB 쓰기를 건너뛸 수 있다.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import Counter, OrderedDict
from copy import deepcopy
from typing import Any


PROFILE_LIST_FIELDS = (
    "regions",
    "cuisines",
    "situations",
    "avoid",
    "liked_shops",
    "disliked_shops",
    "saved_shops",
    "liked_categories",
    "disliked_categories",
)

DEFAULT_PROFILE: dict[str, Any] = {
    "regions": [],
    "cuisines": [],
    "situations": [],
    "budget": "",
    "avoid": [],
    "liked_shops": [],
    "disliked_shops": [],
    "saved_shops": [],
    "liked_categories": [],
    "disliked_categories": [],
}

REGION_KEYWORDS = (
    "강남", "역삼", "선릉", "삼성", "청담", "압구정", "성수", "홍대", "합정",
    "망원", "이태원", "한남", "중구", "을지로", "명동", "종로", "마포",
    "여의도", "잠실", "양재", "도곡", "신촌", "건대", "코엑스",
)

CUISINE_KEYWORDS = (
    "파스타", "이탈리아", "양식", "한식", "중식", "일식", "스시", "초밥",
    "오마카세", "고기", "삼겹살", "갈비", "소고기", "냉면", "평냉", "라면",
    "국밥", "해물", "회", "카페", "브런치", "피자", "버거", "치킨", "와인",
    "주점", "다이닝바", "코스", "파인다이닝",
)

SITUATION_KEYWORDS = (
    "데이트", "혼밥", "회식", "가족", "모임", "점심", "저녁", "아침",
    "소개팅", "기념일", "접대", "가성비", "조용", "분위기", "캐주얼",
)

AVOID_KEYWORDS = (
    "비싼", "비싸", "웨이팅", "웨이팅 긴 곳", "긴 웨이팅", "노키즈",
    "노키즈존", "술집", "술집 분위기", "시끄러운", "오마카세",
)

FOOD_KEYWORDS = set(CUISINE_KEYWORDS) | {
    "식당", "맛집", "밥", "음식", "먹", "레스토랑", "메뉴", "맛",
}
GENERIC_RECOMMENDATION_KEYWORDS = {
    "추천", "찾아", "찾고", "골라", "어디", "뭐 먹", "먹을까",
}
OUT_OF_SCOPE_KEYWORDS = {
    "주가", "주식", "삼성전자", "코인", "비트코인", "환율", "부동산",
    "날씨", "정치", "선거", "전망", "대출", "보험", "병원", "의사",
}
SINGLE_TOKEN_PATTERNS = {
    "회": re.compile(r"(^|[^가-힣])회($|[^가-힣])|횟집|생선회"),
}
SLOT_KEYS = ("regions", "cuisines", "situations")
DIRECT_AVOID_KEYWORDS = {"웨이팅 긴 곳", "긴 웨이팅", "노키즈", "노키즈존", "술집 분위기"}
MEMORY_BACKEND = os.getenv("CHATBOT_MEMORY_BACKEND", "database").strip().lower()
logger = logging.getLogger(__name__)


def empty_profile() -> dict[str, Any]:
    return deepcopy(DEFAULT_PROFILE)


def _append_unique(values: list[str], item: str, limit: int = 20) -> list[str]:
    item = str(item or "").strip()
    if not item:
        return values
    if item not in values:
        values.append(item)
    return values[-limit:]


def _normalize_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    normalized = empty_profile()
    if not isinstance(profile, dict):
        return normalized

    for key in PROFILE_LIST_FIELDS:
        raw_values = profile.get(key) or []
        if isinstance(raw_values, str):
            raw_values = [raw_values]
        if isinstance(raw_values, list):
            for value in raw_values:
                _append_unique(normalized[key], str(value).strip())

    budget = str(profile.get("budget") or "").strip()
    if budget:
        normalized["budget"] = budget

    return normalized


def merge_profiles(base: dict[str, Any] | None, incoming: dict[str, Any] | None) -> dict[str, Any]:
    merged = _normalize_profile(base)
    incoming_profile = _normalize_profile(incoming)
    for key in PROFILE_LIST_FIELDS:
        for value in incoming_profile[key]:
            _append_unique(merged[key], value)
    if incoming_profile.get("budget"):
        merged["budget"] = incoming_profile["budget"]
    return merged


def _contains_keyword(text: str, keyword: str) -> bool:
    if keyword in SINGLE_TOKEN_PATTERNS:
        return bool(SINGLE_TOKEN_PATTERNS[keyword].search(text))
    return keyword in text


def extract_preferences(message: str) -> dict[str, Any]:
    text = str(message or "")
    profile = empty_profile()

    for keyword in REGION_KEYWORDS:
        if _contains_keyword(text, keyword):
            _append_unique(profile["regions"], keyword)
    for keyword in CUISINE_KEYWORDS:
        if _contains_keyword(text, keyword):
            _append_unique(profile["cuisines"], keyword)
    for keyword in SITUATION_KEYWORDS:
        if _contains_keyword(text, keyword):
            _append_unique(profile["situations"], keyword)
    for keyword in AVOID_KEYWORDS:
        should_avoid = (
            "싫" in text
            or "말고" in text
            or "빼" in text
            or "피해" in text
            or "제외" in text
            or "없는" in text
            or "적은" in text
            or "비싸지" in text
            or keyword in DIRECT_AVOID_KEYWORDS
        )
        if _contains_keyword(text, keyword) and should_avoid:
            _append_unique(profile["avoid"], keyword)

    if any(keyword in text for keyword in ("고급", "비싸도", "비싸도 됨", "파인다이닝", "기념일")):
        profile["budget"] = "비싸도 됨"
    elif any(keyword in text for keyword in ("중간", "보통", "적당")):
        profile["budget"] = "중간"
    elif any(keyword in text for keyword in ("가성비", "저렴", "비싸지", "무난", "싼 곳", "싸게")):
        profile["budget"] = "가성비"

    return profile


def is_food_related(message: str) -> bool:
    text = str(message or "")
    has_food_keyword = any(_contains_keyword(text, keyword) for keyword in FOOD_KEYWORDS)
    has_place_or_situation = any(
        _contains_keyword(text, keyword)
        for keyword in set(REGION_KEYWORDS) | set(SITUATION_KEYWORDS)
    )
    has_recommendation_intent = any(keyword in text for keyword in GENERIC_RECOMMENDATION_KEYWORDS)
    has_out_of_scope_signal = any(keyword in text for keyword in OUT_OF_SCOPE_KEYWORDS)

    if has_out_of_scope_signal and not has_food_keyword:
        return False
    if has_food_keyword:
        return True
    return has_place_or_situation and has_recommendation_intent


def missing_slots(message: str, profile: dict[str, Any]) -> list[str]:
    text = str(message or "")
    missing: list[str] = []
    if not profile.get("regions") and not any(_contains_keyword(text, keyword) for keyword in REGION_KEYWORDS):
        missing.append("지역")
    if not profile.get("cuisines") and not any(_contains_keyword(text, keyword) for keyword in CUISINE_KEYWORDS):
        missing.append("메뉴")
    if not profile.get("situations") and not any(_contains_keyword(text, keyword) for keyword in SITUATION_KEYWORDS):
        missing.append("상황")
    return missing


def _has_any_slot(profile: dict[str, Any], keys: tuple[str, ...] = SLOT_KEYS) -> bool:
    return any(profile.get(key) for key in keys)


def _has_slot(profile: dict[str, Any], key: str) -> bool:
    return bool(profile.get(key))


def _wants_saved_profile(message: str) -> bool:
    text = str(message or "")
    return any(keyword in text for keyword in ("내 취향", "저장한 취향", "취향 기준", "알아서", "기억한"))


def should_ask_clarification(
    message: str,
    profile: dict[str, Any],
    current_profile: dict[str, Any] | None = None,
) -> bool:
    if not is_food_related(message):
        return False
    text = str(message or "").strip()
    if _wants_saved_profile(text):
        return False

    current = current_profile or extract_preferences(text)
    current_has_region = _has_slot(current, "regions")
    current_has_cuisine = _has_slot(current, "cuisines")
    current_has_situation = _has_slot(current, "situations")
    current_has_any = _has_any_slot(current)

    broad_patterns = ("맛집 추천", "식당 추천", "뭐 먹", "추천해줘", "추천해 줘", "먹을까")
    if len(text) <= 8 and not current_has_any:
        return True

    if current_has_cuisine and not current_has_region and not current_has_situation:
        return False

    if current_has_region and not current_has_cuisine and not current_has_situation:
        return True
    if current_has_region and current_has_situation and not current_has_cuisine:
        return True
    if current_has_situation and not current_has_region and not current_has_cuisine:
        return True

    if current_has_any:
        return False

    if _has_any_slot(profile) and not any(pattern in text for pattern in broad_patterns):
        return False
    return any(pattern in text for pattern in broad_patterns)


def clarification_question(
    profile: dict[str, Any],
    message: str = "",
    current_profile: dict[str, Any] | None = None,
) -> str:
    current = current_profile or extract_preferences(message)
    current_has_region = _has_slot(current, "regions")
    current_has_cuisine = _has_slot(current, "cuisines")
    current_has_situation = _has_slot(current, "situations")

    if current_has_region and not current_has_cuisine and not current_has_situation:
        region = current["regions"][0]
        return f"{region} 기준이면 어떤 상황과 메뉴가 좋으세요? 예: 데이트 파스타, 혼밥 한식, 회식 고기"
    if current_has_region and current_has_situation and not current_has_cuisine:
        situation = current["situations"][0]
        return f"{situation}용이면 어떤 메뉴가 좋으세요? 예: 파스타, 한식, 고기, 카페"
    if current_has_situation and not current_has_region:
        return "어느 지역에서 찾을까요? 예: 강남, 성수, 중구"

    missing = missing_slots("", profile)
    if "지역" in missing and "메뉴" in missing:
        return "어느 지역에서 어떤 메뉴를 찾고 계세요? 예: 성수 파스타, 중구 평냉, 강남 고기"
    if "지역" in missing:
        return "어느 지역 기준으로 추천해드릴까요?"
    if "메뉴" in missing:
        return "선호하는 메뉴나 음식 종류가 있을까요?"
    return "데이트, 혼밥, 회식처럼 어떤 상황인지 알려주시면 더 정확히 추천해드릴게요."


def clarification_suggestions(
    profile: dict[str, Any],
    message: str = "",
    current_profile: dict[str, Any] | None = None,
) -> list[str]:
    current = current_profile or extract_preferences(message)
    region = (current.get("regions") or profile.get("regions") or ["강남"])[0]
    situation = (current.get("situations") or profile.get("situations") or ["데이트"])[0]

    if current.get("regions") and not current.get("cuisines") and not current.get("situations"):
        return [
            f"{region} 데이트 파스타",
            f"{region} 혼밥 한식",
            f"{region} 회식 고기",
        ]
    if current.get("regions") and current.get("situations") and not current.get("cuisines"):
        return [
            f"{region} {situation} 파스타",
            f"{region} {situation} 한식",
            f"{region} {situation} 고기",
        ]
    if current.get("situations") and not current.get("regions"):
        return [
            f"강남 {situation} 고기",
            f"성수 {situation} 파스타",
            f"중구 {situation} 평냉",
        ]
    return ["강남 데이트 파스타", "중구 평냉 가성비", "성수 카페"]


def profile_summary(profile: dict[str, Any]) -> str:
    parts: list[str] = []
    if profile.get("regions"):
        parts.append("지역 " + ", ".join(profile["regions"][:4]))
    if profile.get("cuisines"):
        parts.append("메뉴 " + ", ".join(profile["cuisines"][:4]))
    if profile.get("situations"):
        parts.append("상황 " + ", ".join(profile["situations"][:4]))
    if profile.get("budget"):
        parts.append("예산 " + profile["budget"])
    if profile.get("liked_categories"):
        parts.append("선호 " + ", ".join(profile["liked_categories"][:3]))
    if profile.get("avoid"):
        parts.append("회피 " + ", ".join(profile["avoid"][:3]))
    return " · ".join(parts) if parts else "아직 저장된 취향이 없습니다."


class PersonalizationStore:
    def __init__(self, max_sessions: int = 200, ttl_seconds: int = 60 * 60 * 24) -> None:
        self._sessions: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._max_sessions = max_sessions
        self._ttl_seconds = ttl_seconds
        self._backend = "memory" if MEMORY_BACKEND == "memory" else "database"

    @property
    def backend(self) -> str:
        return self._backend

    def _db_enabled(self) -> bool:
        return self._backend == "database"

    @staticmethod
    def _parse_json(raw: str | None, fallback: dict[str, Any]) -> dict[str, Any]:
        if not raw:
            return deepcopy(fallback)
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return deepcopy(fallback)
        return payload if isinstance(payload, dict) else deepcopy(fallback)

    def _load_persistent_entry(self, session_id: str) -> dict[str, Any] | None:
        if not self._db_enabled():
            return None
        try:
            from app.database import SessionLocal
            from app.db_models import ChatbotMemory

            db = SessionLocal()
            try:
                row = db.query(ChatbotMemory).filter(ChatbotMemory.session_id == session_id).first()
                if row is None:
                    return None
                profile = merge_profiles(None, self._parse_json(row.profile_json, DEFAULT_PROFILE))
                feedback_raw = self._parse_json(row.feedback_json, {})
                feedback = {
                    str(shop_id): str(action)
                    for shop_id, action in feedback_raw.items()
                    if str(action) in {"like", "dislike", "save"}
                }
                return {"profile": profile, "feedback": feedback}
            finally:
                db.close()
        except Exception as exc:
            logger.warning("챗봇 장기 메모리 로드 실패(session=%s): %s", session_id, exc)
            return None

    def _persist_entry(self, session_id: str, entry: dict[str, Any]) -> None:
        if not self._db_enabled():
            return
        try:
            from app.database import SessionLocal
            from app.db_models import ChatbotMemory

            db = SessionLocal()
            try:
                row = db.query(ChatbotMemory).filter(ChatbotMemory.session_id == session_id).first()
                if row is None:
                    row = ChatbotMemory(session_id=session_id)
                    db.add(row)
                row.profile_json = json.dumps(
                    _normalize_profile(entry.get("profile")),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                row.feedback_json = json.dumps(
                    dict(entry.get("feedback") or {}),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("챗봇 장기 메모리 저장 실패(session=%s): %s", session_id, exc)

    def _delete_persistent_entry(self, session_id: str) -> None:
        if not self._db_enabled():
            return
        try:
            from app.database import SessionLocal
            from app.db_models import ChatbotMemory

            db = SessionLocal()
            try:
                row = db.query(ChatbotMemory).filter(ChatbotMemory.session_id == session_id).first()
                if row is not None:
                    db.delete(row)
                    db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning("챗봇 장기 메모리 삭제 실패(session=%s): %s", session_id, exc)

    def _get_entry(self, session_id: str) -> dict[str, Any]:
        now = time.time()
        self._prune(now)
        if session_id not in self._sessions:
            persistent = self._load_persistent_entry(session_id) or {}
            self._sessions[session_id] = {
                "profile": persistent.get("profile") or empty_profile(),
                "feedback": persistent.get("feedback") or {},
                "created_at": now,
                "last_access": now,
            }
        entry = self._sessions[session_id]
        entry["last_access"] = now
        self._sessions.move_to_end(session_id)
        return entry

    def _prune(self, now: float | None = None) -> None:
        now = now or time.time()
        expired = [
            session_id
            for session_id, entry in self._sessions.items()
            if now - float(entry.get("last_access", now)) > self._ttl_seconds
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)

    def update_from_message(
        self,
        session_id: str,
        message: str,
        client_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = self._get_entry(session_id)
        profile = merge_profiles(entry["profile"], client_profile)
        profile = merge_profiles(profile, extract_preferences(message))
        entry["profile"] = profile
        self._persist_entry(session_id, entry)
        return profile

    def get_profile(self, session_id: str) -> dict[str, Any]:
        return deepcopy(self._get_entry(session_id)["profile"])

    def get_feedback(self, session_id: str) -> dict[str, str]:
        return dict(self._get_entry(session_id)["feedback"])

    def record_feedback(
        self,
        session_id: str,
        shop_id: str,
        action: str,
        shop: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = self._get_entry(session_id)
        action = action if action in {"like", "dislike", "save"} else "like"
        entry["feedback"][shop_id] = action

        profile = entry["profile"]
        if action == "like":
            _append_unique(profile["liked_shops"], shop_id)
        elif action == "dislike":
            _append_unique(profile["disliked_shops"], shop_id)
        elif action == "save":
            _append_unique(profile["saved_shops"], shop_id)
            _append_unique(profile["liked_shops"], shop_id)

        if isinstance(shop, dict):
            for category in shop.get("categories") or []:
                if action in {"like", "save"}:
                    _append_unique(profile["liked_categories"], category)
                elif action == "dislike":
                    _append_unique(profile["disliked_categories"], category)

        self._persist_entry(session_id, entry)

        return {
            "profile": deepcopy(profile),
            "summary": profile_summary(profile),
            "feedback_counts": dict(Counter(entry["feedback"].values())),
        }

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._delete_persistent_entry(session_id)

    def stats(self) -> dict[str, Any]:
        self._prune()
        return {"session_count": len(self._sessions), "storage": self._backend}


personalization_store = PersonalizationStore()
