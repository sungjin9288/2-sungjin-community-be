import json

from app.chatbot.personalization import personalization_store
from app.db_models import ChatbotMemory
from app.database import SessionLocal


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def _signup_and_login(client, email: str, password: str, nickname: str) -> dict:
    signup_res = client.post(
        "/auth/signup",
        json={"email": email, "password": password, "nickname": nickname},
    )
    assert signup_res.status_code == 201

    login_res = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    return login_res.json()["data"]


def test_chatbot_clarifies_broad_food_request(client):
    res = client.post(
        "/chatbot/chat",
        json={
            "message": "맛집 추천",
            "session_id": "pytest_chatbot_clarify",
        },
    )

    assert res.status_code == 200
    payload = res.json()["data"]
    assert payload["clarification"] is True
    assert payload["recommended"] == []
    assert "지역" in payload["reply"] or "메뉴" in payload["reply"]


def test_chatbot_status_exposes_rank_weight_source(client):
    res = client.get("/chatbot/status")

    assert res.status_code == 200
    engine_status = res.json()["data"]["recommendation_engine"]
    assert "rank_weight_source" in engine_status
    assert isinstance(engine_status["rank_weight_source"], str)


def test_chatbot_clarifies_region_only_request(client):
    res = client.post(
        "/chatbot/chat",
        json={
            "message": "성수 맛집 추천해줘",
            "session_id": "pytest_chatbot_region_only",
        },
    )

    assert res.status_code == 200
    payload = res.json()["data"]
    assert payload["clarification"] is True
    assert payload["recommended"] == []
    assert "상황" in payload["reply"] or "메뉴" in payload["reply"]
    assert any("성수" in item for item in payload["next_questions"])


def test_chatbot_ranks_specific_food_request_without_clarification(client):
    res = client.post(
        "/chatbot/chat",
        json={
            "message": "라면 맛집 추천해줘",
            "session_id": "pytest_chatbot_ramen",
        },
    )

    assert res.status_code == 200
    payload = res.json()["data"]
    assert payload["clarification"] is False
    assert isinstance(payload["recommended"], list)


def test_chatbot_prioritizes_explicit_cuisine_matches(client):
    res = client.post(
        "/chatbot/chat",
        json={
            "message": "강남 데이트 파스타 맛집 추천해줘",
            "session_id": "pytest_chatbot_explicit_pasta",
        },
    )

    assert res.status_code == 200
    payload = res.json()["data"]
    assert payload["clarification"] is False
    for shop in payload["recommended"]:
        text = " ".join(
            [
                " ".join(shop.get("categories") or []),
                " ".join(shop.get("menus") or []),
            ]
        )
        assert any(keyword in text for keyword in ["파스타", "이탈리아", "이탈리안"])


def test_chatbot_rejects_out_of_scope_stock_request(client):
    res = client.post(
        "/chatbot/chat",
        json={
            "message": "삼성전자 주가 좀 전망해줘",
            "session_id": "pytest_chatbot_stock",
        },
    )

    assert res.status_code == 200
    payload = res.json()["data"]
    assert payload["clarification"] is False
    assert payload["recommended"] == []
    assert "식당 추천 봇" in payload["reply"]
    assert payload["profile"]["regions"] == []
    assert payload["intent"]["name"] == "out_of_scope"


def test_chatbot_routes_planned_community_feature_without_recommendations(client):
    res = client.post(
        "/chatbot/chat",
        json={
            "message": "내 북마크랑 알림 요약해줘",
            "session_id": "pytest_chatbot_community_intent",
        },
    )

    assert res.status_code == 200
    payload = res.json()["data"]
    assert payload["recommended"] == []
    assert payload["intent"]["name"] == "community_assistant"
    assert payload["intent"]["supported"] is False
    assert "식당 추천" in payload["reply"]


def test_chatbot_can_show_saved_preference_profile(client):
    session_id = "pytest_chatbot_profile_summary_intent"
    chat_res = client.post(
        "/chatbot/chat",
        json={
            "message": "강남 데이트 파스타 맛집 추천해줘",
            "session_id": session_id,
        },
    )
    assert chat_res.status_code == 200

    profile_res = client.post(
        "/chatbot/chat",
        json={
            "message": "내 취향 보여줘",
            "session_id": session_id,
        },
    )

    assert profile_res.status_code == 200
    payload = profile_res.json()["data"]
    assert payload["recommended"] == []
    assert payload["intent"]["name"] == "preference_profile"
    assert "강남" in payload["reply"]
    assert "파스타" in payload["reply"]

    reset_res = client.post("/chatbot/reset", json={"session_id": session_id})
    assert reset_res.status_code == 200


def test_chatbot_uses_saved_profile_for_followup_recommendation(client):
    session_id = "pytest_chatbot_saved_profile_followup"
    first_res = client.post(
        "/chatbot/chat",
        json={
            "message": "강남 데이트 파스타 맛집 추천해줘",
            "session_id": session_id,
        },
    )
    assert first_res.status_code == 200

    followup_res = client.post(
        "/chatbot/chat",
        json={
            "message": "저장한 취향 기준으로 다시 골라줘",
            "session_id": session_id,
        },
    )

    assert followup_res.status_code == 200
    payload = followup_res.json()["data"]
    assert payload["intent"]["name"] == "restaurant_recommendation"
    assert payload["intent"]["reason"] == "saved_profile_recommendation"
    assert payload["clarification"] is False
    assert isinstance(payload["recommended"], list)
    assert "식당 추천 봇" not in payload["reply"]

    reset_res = client.post("/chatbot/reset", json={"session_id": session_id})
    assert reset_res.status_code == 200


def test_chatbot_uses_client_profile_for_saved_profile_followup(client):
    res = client.post(
        "/chatbot/chat",
        json={
            "message": "저장한 취향 기준으로 다시 골라줘",
            "session_id": "pytest_chatbot_client_profile_followup",
            "profile": {
                "regions": ["강남"],
                "cuisines": ["파스타"],
                "situations": ["데이트"],
            },
        },
    )

    assert res.status_code == 200
    payload = res.json()["data"]
    assert payload["intent"]["name"] == "restaurant_recommendation"
    assert payload["intent"]["reason"] == "saved_profile_recommendation"
    assert "강남" in payload["profile"]["regions"]
    assert "파스타" in payload["profile"]["cuisines"]
    assert "식당 추천 봇" not in payload["reply"]


def test_chatbot_does_not_extract_sashimi_from_hwesik(client):
    res = client.post(
        "/chatbot/chat",
        json={
            "message": "강남 회식 고기집 추천해줘",
            "session_id": "pytest_chatbot_hwesik",
        },
    )

    assert res.status_code == 200
    profile = res.json()["data"]["profile"]
    assert "회식" in profile["situations"]
    assert "고기" in profile["cuisines"]
    assert "회" not in profile["cuisines"]


def test_chatbot_extracts_budget_and_avoid_preferences(client):
    res = client.post(
        "/chatbot/chat",
        json={
            "message": "강남 가족 카페 추천해줘. 예산은 중간이고 웨이팅 긴 곳, 노키즈존은 피해줘",
            "session_id": "pytest_chatbot_budget_avoid",
        },
    )

    assert res.status_code == 200
    profile = res.json()["data"]["profile"]
    assert profile["budget"] == "중간"
    assert "카페" in profile["cuisines"]
    assert "가족" in profile["situations"]
    assert any("웨이팅" in value for value in profile["avoid"])
    assert any("노키즈" in value for value in profile["avoid"])


def test_chatbot_profile_and_feedback_lifecycle(client):
    session_id = "pytest_chatbot_personal"

    chat_res = client.post(
        "/chatbot/chat",
        json={
            "message": "성수 데이트 파스타 맛집 추천해줘",
            "session_id": session_id,
            "profile": {"budget": "가성비"},
        },
    )

    assert chat_res.status_code == 200
    chat_payload = chat_res.json()["data"]
    assert chat_payload["clarification"] is False
    assert "성수" in chat_payload["profile"]["regions"]
    assert "파스타" in chat_payload["profile"]["cuisines"]
    assert "데이트" in chat_payload["profile"]["situations"]
    assert chat_payload["profile"]["budget"] == "가성비"
    assert isinstance(chat_payload["recommended"], list)

    feedback_res = client.post(
        "/chatbot/feedback",
        json={
            "session_id": session_id,
            "shop_id": "pytest-shop-1",
            "action": "save",
            "shop": {
                "shop_id": "pytest-shop-1",
                "categories": ["파스타", "데이트"],
            },
        },
    )

    assert feedback_res.status_code == 200
    feedback_payload = feedback_res.json()["data"]
    assert "pytest-shop-1" in feedback_payload["profile"]["saved_shops"]
    assert "파스타" in feedback_payload["profile"]["liked_categories"]
    assert feedback_payload["feedback_counts"]["save"] == 1

    reset_res = client.post("/chatbot/reset", json={"session_id": session_id})
    assert reset_res.status_code == 200


def test_chatbot_writes_learning_log_for_chat_and_feedback(client, tmp_path, monkeypatch):
    log_path = tmp_path / "chatbot_learning.jsonl"
    monkeypatch.setenv("CHATBOT_LEARNING_LOG_PATH", str(log_path))
    session_id = "pytest_chatbot_learning_log"

    chat_res = client.post(
        "/chatbot/chat",
        json={
            "message": "강남 데이트 파스타 맛집 추천해줘",
            "session_id": session_id,
        },
    )
    assert chat_res.status_code == 200

    feedback_res = client.post(
        "/chatbot/feedback",
        json={
            "session_id": session_id,
            "shop_id": "pytest-shop-learning",
            "action": "like",
            "shop": {
                "shop_id": "pytest-shop-learning",
                "shop_name": "테스트 파스타",
                "categories": ["파스타"],
                "score": 0.91,
                "score_breakdown": {
                    "bm25": 0.8,
                    "intent": 0.7,
                    "popularity": 0.2,
                    "personal": 0.5,
                },
                "reasons": ["검색어와 매장 정보가 잘 맞음"],
            },
        },
    )
    assert feedback_res.status_code == 200

    events = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    chat_event = next(
        event
        for event in events
        if event["event_type"] == "chat" and event["session_id"] == session_id
    )
    feedback_event = next(
        event
        for event in events
        if event["event_type"] == "feedback" and event["session_id"] == session_id
    )

    assert chat_event["message"] == "강남 데이트 파스타 맛집 추천해줘"
    assert chat_event["intent"]["name"] == "restaurant_recommendation"
    assert "profile" in chat_event
    assert isinstance(chat_event["recommendations"], list)
    assert feedback_event["action"] == "like"
    assert feedback_event["shop"]["score_breakdown"]["bm25"] == 0.8


def test_chatbot_profile_persists_in_database(client):
    session_id = "pytest_chatbot_persistent_memory"

    chat_res = client.post(
        "/chatbot/chat",
        json={
            "message": "강남 데이트 파스타 비싸도 됨",
            "session_id": session_id,
        },
    )
    assert chat_res.status_code == 200

    db = SessionLocal()
    try:
        row = db.query(ChatbotMemory).filter(ChatbotMemory.session_id == session_id).first()
        assert row is not None
    finally:
        db.close()

    personalization_store._sessions.clear()
    profile_res = client.get("/chatbot/profile", params={"session_id": session_id})

    assert profile_res.status_code == 200
    profile = profile_res.json()["data"]["profile"]
    assert "강남" in profile["regions"]
    assert "파스타" in profile["cuisines"]
    assert "데이트" in profile["situations"]
    assert profile["budget"] == "비싸도 됨"
    assert "비싸" not in profile["avoid"]

    reset_res = client.post("/chatbot/reset", json={"session_id": session_id})
    assert reset_res.status_code == 200

    personalization_store._sessions.clear()
    profile_after_reset = client.get("/chatbot/profile", params={"session_id": session_id})
    assert profile_after_reset.status_code == 200
    assert profile_after_reset.json()["data"]["profile"]["regions"] == []


def test_chatbot_profile_follows_authenticated_user_across_sessions(
    client,
    unique_email,
    unique_nickname,
):
    password = "Abcd1234!"
    tokens = _signup_and_login(
        client,
        unique_email("chatbot-account"),
        password,
        unique_nickname("ca"),
    )
    headers = _auth_header(tokens["access_token"])
    me_res = client.get("/users/me", headers=headers)
    assert me_res.status_code == 200
    user_id = me_res.json()["data"]["id"]

    first_session = "pytest_account_profile_first"
    second_session = "pytest_account_profile_second"
    chat_res = client.post(
        "/chatbot/chat",
        headers=headers,
        json={
            "message": "강남 데이트 파스타 맛집 추천해줘",
            "session_id": first_session,
        },
    )
    assert chat_res.status_code == 200
    assert chat_res.json()["data"]["memory_scope"] == "user"

    db = SessionLocal()
    try:
        user_memory = db.query(ChatbotMemory).filter(ChatbotMemory.session_id == f"user:{user_id}").first()
        session_memory = db.query(ChatbotMemory).filter(ChatbotMemory.session_id == first_session).first()
        assert user_memory is not None
        assert session_memory is None
    finally:
        db.close()

    personalization_store._sessions.clear()
    profile_res = client.get(
        "/chatbot/profile",
        headers=headers,
        params={"session_id": second_session},
    )
    assert profile_res.status_code == 200
    profile_payload = profile_res.json()["data"]
    assert profile_payload["memory_scope"] == "user"
    assert "강남" in profile_payload["profile"]["regions"]
    assert "파스타" in profile_payload["profile"]["cuisines"]

    anon_profile_res = client.get("/chatbot/profile", params={"session_id": second_session})
    assert anon_profile_res.status_code == 200
    anon_payload = anon_profile_res.json()["data"]
    assert anon_payload["memory_scope"] == "session"
    assert anon_payload["profile"]["regions"] == []

    other_tokens = _signup_and_login(
        client,
        unique_email("chatbot-other"),
        password,
        unique_nickname("co"),
    )
    other_profile_res = client.get(
        "/chatbot/profile",
        headers=_auth_header(other_tokens["access_token"]),
        params={"session_id": second_session},
    )
    assert other_profile_res.status_code == 200
    other_payload = other_profile_res.json()["data"]
    assert other_payload["memory_scope"] == "user"
    assert other_payload["profile"]["regions"] == []

    reset_res = client.post(
        "/chatbot/reset",
        headers=headers,
        json={"session_id": second_session},
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["data"]["memory_scope"] == "user"

    personalization_store._sessions.clear()
    after_reset_res = client.get(
        "/chatbot/profile",
        headers=headers,
        params={"session_id": first_session},
    )
    assert after_reset_res.status_code == 200
    assert after_reset_res.json()["data"]["profile"]["regions"] == []
