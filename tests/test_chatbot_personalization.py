from app.chatbot.personalization import personalization_store
from app.db_models import ChatbotMemory
from app.database import SessionLocal


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
