"""
chatbot_chain.py

식당 추천 챗봇 LangChain 체인.

LLM 제공자: LLM_PROVIDER 환경변수로 선택
  gemini : Google Gemini API (GOOGLE_API_KEY 필요)
  ollama : 로컬 Ollama 서버 (OLLAMA_BASE_URL, OLLAMA_MODEL)
  mock   : API 키 없이 규칙 기반 응답

대화 메모리: ConversationBufferWindowMemory(k=5) — 서버 인메모리, 단일 세션
"""

from __future__ import annotations

import logging
import os
import time
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# 시스템 프롬프트
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """당신은 식당 추천 전문 AI 봇입니다.

[규칙]
1. 아래 [추천 식당 목록]에 있는 식당만 추천하세요.
2. 목록에 없는 식당, 웹 검색, 외부 정보는 사용하지 마세요.
3. 식당·음식·지역·맛집과 무관한 질문(주식, 날씨, 정치 등)은 정중히 거절하세요.
   거절 예시: "저는 식당 추천 봇입니다. 죄송하지만 식당 관련 질의해 주시겠어요?"
4. 추천할 식당이 없으면 "죄송합니다. 조건에 맞는 식당을 찾지 못했습니다."라고 하세요.
5. 추가 조건(가격, 분위기 등)이 필요하면 먼저 질문해도 됩니다.
6. 한국어로 친절하게 답변하세요.
"""

RESTAURANT_CONTEXT_TEMPLATE = """\
[추천 식당 목록]
{restaurants}
"""

NO_RESTAURANT_CONTEXT = "[추천 식당 목록]\n현재 조건에 맞는 식당이 없습니다.\n"
DEFAULT_SESSION_TTL_SECONDS = 60 * 60
DEFAULT_MAX_SESSIONS = 200


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        logger.warning("%s 값이 정수가 아니어서 기본값을 사용합니다: %s", name, default)
        return default
    return value if value > 0 else default


def _format_restaurant(r: dict, rank: int) -> str:
    lines = [f"{rank}. {r.get('shop_name', r.get('shop_id', 'unknown'))}"]
    if r.get("address"):
        lines.append(f"   주소: {r['address']}")
    if r.get("categories"):
        lines.append(f"   종류: {', '.join(r['categories'])}")
    if r.get("menus"):
        lines.append(f"   메뉴: {', '.join(r['menus'][:4])}")
    if r.get("facilities"):
        lines.append(f"   편의: {', '.join(r['facilities'][:3])}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# LLM 팩토리
# --------------------------------------------------------------------------- #
def _build_llm(provider: str) -> Any | None:
    """provider에 맞는 LangChain LLM 객체를 반환. 실패 시 None."""
    if provider == "gemini":
        return _build_gemini_llm()
    if provider == "ollama":
        return _build_ollama_llm()
    logger.info("LLM_PROVIDER=%s → mock 모드", provider)
    return None


def _build_gemini_llm() -> Any | None:
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key.startswith("여기에"):
        logger.warning("GOOGLE_API_KEY 미설정 — mock 모드 사용")
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.3,
            convert_system_message_to_human=True,  # Gemini는 system role 미지원
        )
        logger.info("Gemini LLM 초기화 완료 (model=%s)", model)
        return llm
    except Exception as exc:
        logger.error("Gemini LLM 초기화 실패: %s", exc)
        return None


def _build_ollama_llm() -> Any | None:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    try:
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.3,
        )
        logger.info("Ollama LLM 초기화 완료 (model=%s, url=%s)", model, base_url)
        return llm
    except Exception as exc:
        logger.error("Ollama LLM 초기화 실패: %s", exc)
        return None


# --------------------------------------------------------------------------- #
# 챗봇 체인
# --------------------------------------------------------------------------- #
class ChatbotChain:
    """
    세션 기반 대화 체인을 관리하는 LangChain 래퍼.

    LLM_PROVIDER 값에 따라 gemini / ollama / mock 세 가지 모드로 동작.
    session_id별로 ConversationChain(메모리 포함) 인스턴스를 격리.
    """

    def __init__(self) -> None:
        self._llm: Any = None
        self._sessions: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._provider = os.getenv("LLM_PROVIDER", "mock").lower()
        self._session_ttl_seconds = _positive_int_env(
            "CHATBOT_SESSION_TTL_SECONDS", DEFAULT_SESSION_TTL_SECONDS
        )
        self._max_sessions = _positive_int_env("CHATBOT_MAX_SESSIONS", DEFAULT_MAX_SESSIONS)
        self._initialized = False

    def initialize(self) -> None:
        self._llm = _build_llm(self._provider)
        if self._llm is None:
            self._initialized = False
            logger.info("챗봇 mock 모드로 동작")
            return

        self._initialized = True
        logger.info("챗봇 체인 초기화 완료 (provider=%s)", self._provider)

    def _get_chain(self, session_id: str) -> Any:
        now = time.time()
        self._prune_sessions(now)

        if session_id in self._sessions:
            entry = self._sessions[session_id]
            entry["last_access"] = now
            self._sessions.move_to_end(session_id)
            return entry["chain"]

        try:
            from langchain.chains import ConversationChain
            from langchain.memory import ConversationBufferWindowMemory
            from langchain.prompts import (
                ChatPromptTemplate,
                HumanMessagePromptTemplate,
                MessagesPlaceholder,
                SystemMessagePromptTemplate,
            )

            memory = ConversationBufferWindowMemory(
                k=5,
                return_messages=True,
                memory_key="history",
            )

            prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
                    MessagesPlaceholder(variable_name="history"),
                    HumanMessagePromptTemplate.from_template("{input}"),
                ]
            )

            chain = ConversationChain(
                llm=self._llm,
                memory=memory,
                prompt=prompt,
                verbose=False,
            )
            self._sessions[session_id] = {
                "chain": chain,
                "created_at": now,
                "last_access": now,
            }
            self._prune_sessions(now)
            return chain

        except Exception as exc:
            logger.error("ConversationChain 초기화 실패 (session=%s): %s", session_id, exc)
            return None

    def _prune_sessions(self, now: float | None = None) -> None:
        if not self._sessions:
            return

        now = now or time.time()
        expired = [
            session_id
            for session_id, entry in self._sessions.items()
            if now - float(entry.get("last_access", now)) > self._session_ttl_seconds
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)

        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)

    # ------------------------------------------------------------------ #
    # 대화
    # ------------------------------------------------------------------ #
    def chat(self, user_message: str, recommended_shops: list[dict], session_id: str = "default") -> str:
        if not self._initialized or self._llm is None:
            return self._mock_response(user_message, recommended_shops)

        chain = self._get_chain(session_id)
        if chain is None:
            return "죄송합니다. 챗봇 체인 초기화에 실패했습니다."

        # 추천 식당 컨텍스트 구성
        if recommended_shops:
            restaurants_text = "\n".join(
                _format_restaurant(r, i + 1) for i, r in enumerate(recommended_shops)
            )
            context = RESTAURANT_CONTEXT_TEMPLATE.format(restaurants=restaurants_text)
        else:
            context = NO_RESTAURANT_CONTEXT

        augmented = f"{context}\n사용자 질문: {user_message}"

        try:
            response = chain.predict(input=augmented)
            return self._enforce_recommendation_guard(response, recommended_shops)
        except Exception as exc:
            logger.error("LLM 호출 실패 (provider=%s, session=%s): %s", self._provider, session_id, exc)
            return "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

    def reset_memory(self, session_id: str = "default") -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["chain"].memory.clear()
            self._sessions.pop(session_id, None)
            logger.info("챗봇 대화 기록 초기화 (session=%s)", session_id)

    @staticmethod
    def _verified_recommendation_block(recommended_shops: list[dict]) -> str:
        lines = ["조건에 맞는 식당을 추천해드립니다:\n"]
        for i, shop in enumerate(recommended_shops, 1):
            name = shop.get("shop_name") or shop.get("shop_id", "알 수 없음")
            addr = shop.get("address", "")
            cats = ", ".join(shop.get("categories", [])[:2])
            line = f"{i}. {name}"
            if addr:
                line += f" ({addr[:24]})"
            if cats:
                line += f" — {cats}"
            lines.append(line)
        lines.append("\n아래 추천 카드는 서버 추천 모델 결과만 표시합니다.")
        return "\n".join(lines)

    @classmethod
    def _enforce_recommendation_guard(cls, response: str, recommended_shops: list[dict]) -> str:
        """
        LLM 텍스트가 추천 후보명을 전혀 포함하지 않으면 서버 검증 목록으로 대체한다.
        추천 식당 데이터는 별도 response field에서도 내려가므로, 최종 추천명은 서버 목록을 기준으로 둔다.
        """
        response = str(response or "").strip()
        if not recommended_shops:
            return response or "죄송합니다. 조건에 맞는 식당을 찾지 못했습니다."

        allowed_names = [
            str(shop.get("shop_name") or "").strip()
            for shop in recommended_shops
            if str(shop.get("shop_name") or "").strip()
        ]
        if any(name and name in response for name in allowed_names):
            return response

        return cls._verified_recommendation_block(recommended_shops)

    # ------------------------------------------------------------------ #
    # Mock 응답 (API 키 없을 때)
    # ------------------------------------------------------------------ #
    _FOOD_KEYWORDS = frozenset([
        "식당", "맛집", "추천", "밥", "음식", "먹", "파스타", "라면", "스시",
        "한식", "중식", "일식", "양식", "카페", "고기", "해물", "냉면", "국밥",
        "오마카세", "회", "피자", "버거", "치킨", "갈비", "삼겹살", "초밥",
        "레스토랑", "식사", "메뉴", "맛", "강남", "홍대", "이태원", "성수",
        "데이트", "가족", "혼밥", "회식", "점심", "저녁", "아침",
    ])

    @classmethod
    def _mock_response(cls, user_message: str, recommended_shops: list[dict]) -> str:
        is_food = any(kw in user_message for kw in cls._FOOD_KEYWORDS)

        if not is_food:
            return "저는 식당 추천 봇입니다. 죄송하지만 식당 관련 질의해 주시겠어요?"

        if not recommended_shops:
            return "죄송합니다. 조건에 맞는 식당을 찾지 못했습니다. 다른 조건으로 검색해 주세요."

        lines = ["조건에 맞는 식당을 추천해드립니다:\n"]
        for i, shop in enumerate(recommended_shops, 1):
            name = shop.get("shop_name") or shop.get("shop_id", "알 수 없음")
            addr = shop.get("address", "")
            cats = ", ".join(shop.get("categories", [])[:2])
            line = f"{i}. {name}"
            if addr:
                line += f" ({addr[:20]})"
            if cats:
                line += f" — {cats}"
            lines.append(line)

        lines.append("\n자세한 정보가 필요하시면 말씀해주세요!")
        return "\n".join(lines)


# 싱글턴
chatbot_chain = ChatbotChain()
