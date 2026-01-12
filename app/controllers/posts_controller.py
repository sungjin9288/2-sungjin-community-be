from fastapi.responses import JSONResponse
from app.common.responses import ok, created, bad_request, unauthorized, forbidden, not_found, server_error
from app.common.auth import is_authorized

POSTS = [
    {"post_id": 1, "title": "welcome", "content": "hi", "author": "starter"},
    {"post_id": 2, "title": "rules", "content": "be nice", "author": "admin"},
]

def list_posts(page: int, limit: int, authorization: str | None) -> JSONResponse:
    try:
        if not is_authorized(authorization):
            return unauthorized("unauthorized")

        if page < 1 or limit < 1 or limit > 50:
            return bad_request("invalid_paging_params")

        start = (page - 1) * limit
        end = start + limit
        data = {"page": page, "limit": limit, "items": POSTS[start:end]}
        return ok("read_posts_success", data)
    except Exception:
        return server_error()


def read_post(post_id: int, authorization: str | None) -> JSONResponse:
    try:
        if not is_authorized(authorization):
            return unauthorized("unauthorized")

        post = next((p for p in POSTS if p["post_id"] == post_id), None)
        if post is None:
            return not_found("post_not_found")

        return ok("read_post_success", post)
    except Exception:
        return server_error()


def create_post(payload: dict, authorization: str | None) -> JSONResponse:
    try:
        if not is_authorized(authorization):
            return unauthorized("unauthorized")

        title = payload.get("title")
        content = payload.get("content")
        image_url = payload.get("image_url")

        if not title or not content:
            return bad_request("missing_required_fields")

        new_id = max(p["post_id"] for p in POSTS) + 1 if POSTS else 1
        POSTS.append(
            {"post_id": new_id, "title": title, "content": content, "author": "starter", "image_url": image_url}
        )
        return created("post_created", {"post_id": new_id})
    except Exception:
        return server_error()


def update_post(post_id: int, payload: dict, authorization: str | None) -> JSONResponse:
    try:
        if not is_authorized(authorization):
            return unauthorized("unauthorized")

        post = next((p for p in POSTS if p["post_id"] == post_id), None)
        if post is None:
            return not_found("post_not_found")

        if post["author"] != "starter":
            return forbidden("permission_denied")

        title = payload.get("title")
        content = payload.get("content")
        if not title and not content:
            return bad_request("no_fields_to_update")

        if title:
            post["title"] = title
        if content:
            post["content"] = content

        return ok("post_updated", None)
    except Exception:
        return server_error()


def delete_post(post_id: int, authorization: str | None) -> JSONResponse:
    try:
        if not is_authorized(authorization):
            return unauthorized("unauthorized")

        post = next((p for p in POSTS if p["post_id"] == post_id), None)
        if post is None:
            return not_found("post_not_found")

        if post["author"] != "starter":
            return forbidden("permission_denied")

        POSTS.remove(post)
        return ok("post_deleted", None)
    except Exception:
        return server_error()
