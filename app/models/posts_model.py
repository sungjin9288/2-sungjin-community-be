from __future__ import annotations

from typing import Dict, List, Optional

_posts: Dict[int, dict] = {}
_post_seq: int = 1


def create_post(author_id: int, title: str, content: str, image: Optional[str] = None) -> dict:
    global _post_seq
    post = {
        "id": _post_seq,
        "author_id": author_id,
        "title": title,
        "content": content,
        "image": image,
    }
    _posts[_post_seq] = post
    _post_seq += 1
    return post


def list_posts(page: int, limit: int) -> dict:
    all_posts = sorted(_posts.values(), key=lambda p: p["id"], reverse=True)
    total = len(all_posts)

    start = (page - 1) * limit
    end = start + limit
    items = all_posts[start:end]

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "items": items,
    }


def find_post_by_id(post_id: int) -> Optional[dict]:
    return _posts.get(post_id)


def update_post(post_id: int, title: Optional[str], content: Optional[str], image: Optional[str]) -> Optional[dict]:
    post = _posts.get(post_id)
    if not post:
        return None

    if title is not None:
        post["title"] = title
    if content is not None:
        post["content"] = content
    if image is not None:
        post["image"] = image

    return post


def delete_post(post_id: int) -> bool:
    return _posts.pop(post_id, None) is not None
