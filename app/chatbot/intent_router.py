"""
chatbot intent routing.

챗봇이 여러 기능을 갖는 형태로 확장될 수 있게 사용자 메시지를
기능 단위 intent로 분류한다. 현재 production-ready 기능은 식당 추천이고,
커뮤니티 보조 기능은 명확히 planned 상태로 응답한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.chatbot.personalization import is_food_related


@dataclass(frozen=True)
class IntentRoute:
    name: str
    feature: str
    supported: bool
    reason: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROFILE_SUMMARY_KEYWORDS = ("내 취향", "저장된 취향", "기억한 취향", "취향 프로필")
PROFILE_SUMMARY_ACTIONS = ("보여", "알려", "확인", "요약", "뭐야", "뭐였")
SAVED_RECOMMENDATION_KEYWORDS = ("내 취향", "저장한 취향", "취향 기준", "기억한", "알아서")
RECOMMENDATION_ACTIONS = ("추천", "골라", "찾아", "다시")
COMMUNITY_KEYWORDS = (
    "게시글",
    "글 검색",
    "글 찾아",
    "댓글",
    "북마크",
    "알림",
    "메시지",
    "쪽지",
    "프로필 수정",
    "비밀번호",
    "회원가입",
)
OUT_OF_SCOPE_KEYWORDS = (
    "주가",
    "주식",
    "삼성전자",
    "코인",
    "비트코인",
    "환율",
    "부동산",
    "날씨",
    "정치",
    "선거",
    "전망",
    "대출",
    "보험",
    "병원",
    "의사",
)


def _has_any_profile_value(profile: dict[str, Any] | None) -> bool:
    if not isinstance(profile, dict):
        return False
    for key in (
        "regions",
        "cuisines",
        "situations",
        "avoid",
        "liked_shops",
        "saved_shops",
        "liked_categories",
    ):
        if profile.get(key):
            return True
    return bool(profile.get("budget"))


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_chat_intent(
    message: str,
    profile: dict[str, Any] | None = None,
) -> IntentRoute:
    text = str(message or "").strip()
    if not text:
        return IntentRoute(
            name="empty_message",
            feature="chat",
            supported=False,
            reason="empty",
            confidence=1.0,
        )

    wants_profile_summary = (
        _contains_any(text, PROFILE_SUMMARY_KEYWORDS)
        and _contains_any(text, PROFILE_SUMMARY_ACTIONS)
    )
    if wants_profile_summary:
        return IntentRoute(
            name="preference_profile",
            feature="chatbot_memory",
            supported=True,
            reason="profile_summary_request",
            confidence=0.92,
        )

    wants_saved_recommendation = (
        _contains_any(text, SAVED_RECOMMENDATION_KEYWORDS)
        and _contains_any(text, RECOMMENDATION_ACTIONS)
    )
    if wants_saved_recommendation and _has_any_profile_value(profile):
        return IntentRoute(
            name="restaurant_recommendation",
            feature="restaurant_recommendation",
            supported=True,
            reason="saved_profile_recommendation",
            confidence=0.88,
        )

    if is_food_related(text):
        return IntentRoute(
            name="restaurant_recommendation",
            feature="restaurant_recommendation",
            supported=True,
            reason="food_related",
            confidence=0.9,
        )

    if _contains_any(text, COMMUNITY_KEYWORDS):
        return IntentRoute(
            name="community_assistant",
            feature="community_assistant",
            supported=False,
            reason="planned_community_feature",
            confidence=0.78,
        )

    if _contains_any(text, OUT_OF_SCOPE_KEYWORDS):
        return IntentRoute(
            name="out_of_scope",
            feature="restaurant_recommendation",
            supported=False,
            reason="non_food_domain",
            confidence=0.85,
        )

    return IntentRoute(
        name="out_of_scope",
        feature="restaurant_recommendation",
        supported=False,
        reason="unknown_or_unsupported",
        confidence=0.55,
    )


def supported_features() -> list[dict[str, str]]:
    return [
        {
            "name": "restaurant_recommendation",
            "status": "ready",
            "description": "행동 로그와 개인 취향 기반 식당 추천",
        },
        {
            "name": "chatbot_memory",
            "status": "ready",
            "description": "세션별 취향 프로필 조회와 재추천",
        },
        {
            "name": "community_assistant",
            "status": "planned",
            "description": "게시글, 북마크, 알림, 메시지 조회",
        },
    ]
