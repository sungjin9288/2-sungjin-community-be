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
