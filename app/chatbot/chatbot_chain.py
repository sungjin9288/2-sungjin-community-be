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
    단일 대화 세션을 관리하는 LangChain 래퍼.

    LLM_PROVIDER 값에 따라 gemini / ollama / mock 세 가지 모드로 동작.
    """

    def __init__(self) -> None:
        self._chain: Any = None
        self._memory: Any = None
        self._provider = os.getenv("LLM_PROVIDER", "mock").lower()
        self._initialized = False

    def initialize(self) -> None:
        llm = _build_llm(self._provider)
        if llm is None:
            self._initialized = False
            logger.info("챗봇 mock 모드로 동작")
            return

        try:
            from langchain.chains import ConversationChain
            from langchain.memory import ConversationBufferWindowMemory
            from langchain.prompts import (
                ChatPromptTemplate,
                HumanMessagePromptTemplate,
                MessagesPlaceholder,
                SystemMessagePromptTemplate,
            )

            self._memory = ConversationBufferWindowMemory(
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

            self._chain = ConversationChain(
                llm=llm,
                memory=self._memory,
                prompt=prompt,
                verbose=False,
            )
            self._initialized = True
            logger.info("챗봇 체인 초기화 완료 (provider=%s)", self._provider)

        except Exception as exc:
            logger.error("ConversationChain 초기화 실패: %s", exc)
            self._initialized = False

    # ------------------------------------------------------------------ #
    # 대화
    # ------------------------------------------------------------------ #
    def chat(self, user_message: str, recommended_shops: list[dict]) -> str:
        if not self._initialized or self._chain is None:
            return self._mock_response(user_message, recommended_shops)

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
            response = self._chain.predict(input=augmented)
            return response
        except Exception as exc:
            logger.error("LLM 호출 실패 (provider=%s): %s", self._provider, exc)
            return "죄송합니다. 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

    def reset_memory(self) -> None:
        if self._memory:
            self._memory.clear()
            logger.info("챗봇 대화 기록 초기화")

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
