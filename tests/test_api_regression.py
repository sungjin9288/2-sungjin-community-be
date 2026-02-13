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
