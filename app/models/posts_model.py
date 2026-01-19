
from typing import Optional


_posts: dict[int, dict] = {}
_post_seq: int = 1

# 좋아요 저장소 (user_id, post_id) 조합으로 중복 방지
_likes: set[tuple[int, int]] = set()


def list_posts(page: int = 1, limit: int = 10) -> dict:
 
    items = list(_posts.values())
    items.sort(key=lambda x: x["id"], reverse=True)

    total = len(items)
    start = (page - 1) * limit
    end = start + limit

    sliced = items[start:end]
    
    # 원본 오염 방지: copy로 가공
    view_items: list[dict] = []
    for p in sliced:
        d = p.copy()
        d["likes_count"] = get_like_count(d["id"])
        view_items.append(d)

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "items": view_items
    }


def find_post(post_id: int) -> Optional[dict]:

    return _posts.get(post_id)


def create_post(
    user_id: int,
    title: str,
    content: str,
    image_url: Optional[str] = None
) -> dict:
 
    global _post_seq
    post = {
        "id": _post_seq,
        "user_id": user_id,
        "title": title,
        "content": content,
        "image_url": image_url,
        "views": 0,
    }
    _posts[_post_seq] = post
    _post_seq += 1
    return post


def update_post(
    post_id: int,
    title: str,
    content: str,
    image_url: Optional[str] = None
) -> Optional[dict]:
   
    post = _posts.get(post_id)
    if not post:
        return None
    
    post["title"] = title
    post["content"] = content
    if image_url is not None:
        post["image_url"] = image_url
    
    return post


def delete_post(post_id: int) -> None:

    _posts.pop(post_id, None)
    
  
    to_remove = [(uid, pid) for (uid, pid) in _likes if pid == post_id]
    for t in to_remove:
        _likes.discard(t)


def increment_views(post_id: int) -> None:

    post = _posts.get(post_id)
    if post:
        post["views"] += 1


# ==================== 좋아요 관리 ====================

def add_like(user_id: int, post_id: int) -> None:

    _likes.add((user_id, post_id))


def remove_like(user_id: int, post_id: int) -> None:
 
    _likes.discard((user_id, post_id))


def is_liked(user_id: int, post_id: int) -> bool:

    return (user_id, post_id) in _likes


def get_like_count(post_id: int) -> int:

    return sum(1 for _, pid in _likes if pid == post_id)