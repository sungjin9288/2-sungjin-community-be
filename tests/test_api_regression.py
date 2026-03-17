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
    payload = login_res.json()["data"]
    assert payload["access_token"]
    assert payload["refresh_token"]
    return payload


def test_auth_token_lifecycle(client, unique_email, unique_nickname):
    password = "Abcd1234!"
    tokens = _signup_and_login(client, unique_email("auth"), password, unique_nickname("n"))

    me_before = client.get("/users/me", headers=_auth_header(tokens["access_token"]))
    assert me_before.status_code == 200

    refresh_res = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()["data"]
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    logout_res = client.post("/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert logout_res.status_code == 200

    refresh_again = client.post("/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert refresh_again.status_code == 400


def test_password_change_requires_current_password(client, unique_email, unique_nickname):
    password = "Abcd1234!"
    tokens = _signup_and_login(client, unique_email("pw"), password, unique_nickname("n"))
    headers = _auth_header(tokens["access_token"])

    bad_res = client.patch(
        "/users/me/password",
        headers=headers,
        json={"current_password": "", "new_password": "Qwer1234!"},
    )
    assert bad_res.status_code == 400
    assert bad_res.json()["message"] == "invalid_request_format"

    good_res = client.patch(
        "/users/me/password",
        headers=headers,
        json={"current_password": password, "new_password": "Qwer1234!"},
    )
    assert good_res.status_code == 200


def test_posts_tags_filters_and_trending(client, unique_email, unique_nickname):
    password = "Abcd1234!"
    tokens = _signup_and_login(client, unique_email("feed"), password, unique_nickname("n"))
    headers = _auth_header(tokens["access_token"])

    create_one = client.post(
        "/posts",
        headers=headers,
        json={"title": "Python Post", "content": "content1", "tags": ["python", "backend"]},
    )
    assert create_one.status_code == 201

    create_two = client.post(
        "/posts",
        headers=headers,
        json={"title": "Design Post", "content": "content2", "tags": ["design"]},
    )
    assert create_two.status_code == 201

    tagged = client.get("/posts", params={"tag": "python", "sort": "latest"})
    assert tagged.status_code == 200
    items = tagged.json()["data"]
    assert len(items) == 1
    assert "python" in items[0]["tags"]

    trending = client.get("/posts/trending", params={"days": 7, "limit": 5})
    assert trending.status_code == 200
    payload = trending.json()["data"]
    assert "top_tags" in payload
    assert "posts" in payload
    assert any(tag["name"] == "python" for tag in payload["top_tags"])


def test_like_idempotency(client, unique_email, unique_nickname):
    password = "Abcd1234!"
    tokens = _signup_and_login(client, unique_email("like"), password, unique_nickname("n"))
    headers = _auth_header(tokens["access_token"])

    created = client.post(
        "/posts",
        headers=headers,
        json={"title": "Like Target", "content": "hello", "tags": []},
    )
    assert created.status_code == 201
    post_id = created.json()["data"]["id"]

    first_like = client.post(f"/posts/{post_id}/likes", headers=headers)
    assert first_like.status_code == 201

    second_like = client.post(f"/posts/{post_id}/likes", headers=headers)
    assert second_like.status_code == 400
    assert second_like.json()["message"] == "invalid_request_format"


def test_invalid_sort_rejected(client):
    res = client.get("/posts", params={"sort": "not-supported"})
    assert res.status_code == 400
    assert res.json()["message"] == "invalid_request_format"


def test_direct_messages_lifecycle(client, unique_email, unique_nickname):
    password = "Abcd1234!"
    sender_email = unique_email("sender")
    sender_nickname = unique_nickname("s")
    recipient_email = unique_email("recipient")
    recipient_nickname = unique_nickname("r")

    sender_tokens = _signup_and_login(client, sender_email, password, sender_nickname)
    recipient_tokens = _signup_and_login(client, recipient_email, password, recipient_nickname)

    sender_headers = _auth_header(sender_tokens["access_token"])
    recipient_headers = _auth_header(recipient_tokens["access_token"])

    search_res = client.get(
        "/messages/users",
        headers=sender_headers,
        params={"query": recipient_nickname[:3]},
    )
    assert search_res.status_code == 200
    users = search_res.json()["data"]
    recipient_user = next((item for item in users if item["email"] == recipient_email), None)
    assert recipient_user is not None

    send_res = client.post(
        "/messages",
        headers=sender_headers,
        json={"recipient_id": recipient_user["id"], "content": "안녕하세요, DM 테스트입니다."},
    )
    assert send_res.status_code == 201
    sent_payload = send_res.json()["data"]
    assert sent_payload["is_mine"] is True
    assert sent_payload["recipient"]["id"] == recipient_user["id"]

    unread_res = client.get("/messages/unread-count", headers=recipient_headers)
    assert unread_res.status_code == 200
    assert unread_res.json()["data"]["unread_count"] == 1

    conversations_res = client.get("/messages/conversations", headers=recipient_headers)
    assert conversations_res.status_code == 200
    conversations = conversations_res.json()["data"]
    assert len(conversations) == 1
    assert conversations[0]["unread_count"] == 1
    assert conversations[0]["partner"]["email"] == sender_email

    sender_user_id = sent_payload["sender"]["id"]
    recipient_thread_res = client.get(f"/messages/with/{sender_user_id}", headers=recipient_headers)
    assert recipient_thread_res.status_code == 200
    thread = recipient_thread_res.json()["data"]
    assert len(thread) == 1
    assert thread[0]["content"] == "안녕하세요, DM 테스트입니다."
    assert thread[0]["is_mine"] is False

    conversations_after_res = client.get("/messages/conversations", headers=recipient_headers)
    assert conversations_after_res.status_code == 200
    assert conversations_after_res.json()["data"][0]["unread_count"] == 0


def test_bookmarks_notifications_blocks_and_reports(client, unique_email, unique_nickname):
    password = "Abcd1234!"
    author = _signup_and_login(client, unique_email("author"), password, unique_nickname("a"))
    reader = _signup_and_login(client, unique_email("reader"), password, unique_nickname("r"))

    author_headers = _auth_header(author["access_token"])
    reader_headers = _auth_header(reader["access_token"])

    post_res = client.post(
        "/posts",
        headers=author_headers,
        json={"title": "북마크 테스트", "content": "본문", "tags": ["qa"]},
    )
    assert post_res.status_code == 201
    post_id = post_res.json()["data"]["id"]

    bookmark_res = client.post(f"/posts/{post_id}/bookmarks", headers=reader_headers)
    assert bookmark_res.status_code == 201

    my_bookmarks_res = client.get("/posts/bookmarks/me", headers=reader_headers)
    assert my_bookmarks_res.status_code == 200
    assert my_bookmarks_res.json()["data"][0]["id"] == post_id
    assert my_bookmarks_res.json()["data"][0]["is_bookmarked"] is True

    comment_res = client.post(
        f"/posts/{post_id}/comments",
        headers=reader_headers,
        json={"content": "좋은 글이네요!"},
    )
    assert comment_res.status_code == 201
    comment_id = comment_res.json()["data"]["id"]

    notifications_res = client.get("/notifications", headers=author_headers)
    assert notifications_res.status_code == 200
    notifications = notifications_res.json()["data"]
    assert any(item["type"] == "comment" for item in notifications)

    report_res = client.post(
        "/reports",
        headers=reader_headers,
        json={"target_type": "post", "target_id": post_id, "reason": "etc", "description": "검증용 신고"},
    )
    assert report_res.status_code == 201

    reply_res = client.post(
        f"/posts/{post_id}/comments",
        headers=author_headers,
        json={"content": "답글입니다.", "parent_comment_id": comment_id},
    )
    assert reply_res.status_code == 201

    nested_comments_res = client.get(f"/posts/{post_id}/comments", headers=author_headers)
    assert nested_comments_res.status_code == 200
    nested_comments = nested_comments_res.json()["data"]
    assert len(nested_comments) == 1
    assert len(nested_comments[0]["replies"]) == 1

    author_me = client.get("/users/me", headers=author_headers)
    author_user_id = author_me.json()["data"]["id"]
    block_res = client.post(f"/blocks/users/{author_user_id}", headers=reader_headers)
    assert block_res.status_code == 201

    hidden_posts_res = client.get("/posts", headers=reader_headers)
    assert hidden_posts_res.status_code == 200
    assert hidden_posts_res.json()["data"] == []

    blocked_dm_res = client.post(
        "/messages",
        headers=reader_headers,
        json={"recipient_id": author_user_id, "content": "차단 후 DM"},
    )
    assert blocked_dm_res.status_code == 403

    hidden_comments_res = client.get(f"/posts/{post_id}/comments", headers=reader_headers)
    assert hidden_comments_res.status_code == 404
