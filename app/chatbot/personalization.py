"""
personalization.py

식당 추천 챗봇의 세션별 취향 프로필과 피드백을 관리한다.

영속 DB를 추가하지 않고 LocalStorage payload + 서버 인메모리 세션 상태를 병합한다.
나중에 Redis/DB로 옮길 수 있도록 순수 dict 기반 인터페이스로 유지한다.
"""

from __future__ import annotations

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
    "비싼", "비싸", "웨이팅", "노키즈", "술집", "시끄러운", "오마카세",
)

FOOD_KEYWORDS = set(CUISINE_KEYWORDS) | {
    "식당", "맛집", "추천", "밥", "음식", "먹", "레스토랑", "메뉴", "맛",
}
SINGLE_TOKEN_PATTERNS = {
    "회": re.compile(r"(^|[^가-힣])회($|[^가-힣])|횟집|생선회"),
}


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
        if _contains_keyword(text, keyword) and ("싫" in text or "말고" in text or "빼" in text or keyword in ("비싼", "비싸")):
            _append_unique(profile["avoid"], keyword)

    if any(keyword in text for keyword in ("가성비", "저렴", "싸", "비싸지", "무난")):
        profile["budget"] = "가성비"
    elif any(keyword in text for keyword in ("고급", "비싸도", "파인다이닝", "기념일")):
        profile["budget"] = "프리미엄"

    return profile


def is_food_related(message: str) -> bool:
    text = str(message or "")
    return any(_contains_keyword(text, keyword) for keyword in FOOD_KEYWORDS | set(REGION_KEYWORDS) | set(SITUATION_KEYWORDS))


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


def should_ask_clarification(message: str, profile: dict[str, Any]) -> bool:
    if not is_food_related(message):
        return False
    text = str(message or "").strip()
    broad_patterns = ("맛집 추천", "식당 추천", "뭐 먹", "추천해줘", "추천해 줘")
    has_concrete_slot = any(profile.get(key) for key in ("regions", "cuisines", "situations"))
    if len(text) <= 8 and not has_concrete_slot:
        return True
    if has_concrete_slot:
        return False
    return any(pattern in text for pattern in broad_patterns)


def clarification_question(profile: dict[str, Any]) -> str:
    missing = missing_slots("", profile)
    if "지역" in missing and "메뉴" in missing:
        return "어느 지역에서 어떤 메뉴를 찾고 계세요? 예: 성수 파스타, 중구 평냉, 강남 고기"
    if "지역" in missing:
        return "어느 지역 기준으로 추천해드릴까요?"
    if "메뉴" in missing:
        return "선호하는 메뉴나 음식 종류가 있을까요?"
    return "데이트, 혼밥, 회식처럼 어떤 상황인지 알려주시면 더 정확히 추천해드릴게요."


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

    def _get_entry(self, session_id: str) -> dict[str, Any]:
        now = time.time()
        self._prune(now)
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "profile": empty_profile(),
                "feedback": {},
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

        return {
            "profile": deepcopy(profile),
            "summary": profile_summary(profile),
            "feedback_counts": dict(Counter(entry["feedback"].values())),
        }

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def stats(self) -> dict[str, Any]:
        self._prune()
        return {"session_count": len(self._sessions)}


personalization_store = PersonalizationStore()
