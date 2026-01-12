from fastapi.responses import JSONResponse
from app.common.responses import ok, created, bad_request, unauthorized, forbidden, not_found, server_error
from app.common.auth import is_authorized

COMMENTS = {
    1: [{"comment_id": 1, "content": "nice", "author": "starter"}],
    2: [],
}

def list_comments(post_id: int, authorization: str | None) -> JSONResponse:
    try:
        if not is_authorized(authorization):
            return unauthorized("unauthorized")

        items = COMMENTS.get(post_id)
        if items is None:
            return not_found("post_not_found")

        return ok("read_comments_success", {"items": items})
    except Exception:
        return server_error()


def create_comment(post_id: int, payload: dict, authorization: str | None) -> JSONResponse:
    try:
        if not is_authorized(authorization):
            return unauthorized("unauthorized")

        content = payload.get("content")
        if not content:
            return bad_request("missing_required_fields")

        items = COMMENTS.get(post_id)
        if items is None:
            return not_found("post_not_found")

        new_id = max([c["comment_id"] for c in items], default=0) + 1
        items.append({"comment_id": new_id, "content": content, "author": "starter"})
        return created("comment_created", {"comment_id": new_id})
    except Exception:
        return server_error()


def delete_comment(post_id: int, comment_id: int, authorization: str | None) -> JSONResponse:
    try:
        if not is_authorized(authorization):
            return unauthorized("unauthorized")

        items = COMMENTS.get(post_id)
        if items is None:
            return not_found("post_not_found")

        target = next((c for c in items if c["comment_id"] == comment_id), None)
        if target is None:
            return not_found("comment_not_found")

        if target["author"] != "starter":
            return forbidden("permission_denied")

        items.remove(target)
        return ok("comment_deleted", None)
    except Exception:
        return server_error()
