_posts: dict[int, dict] = {}
_post_seq: int = 1
_likes: set[tuple[int, int]] = set()  # (user_id, post_id)

def list_posts(page: int = 1, limit: int = 10) -> dict:
    items = list(_posts.values())
    for item in items:
        item["likes_count"] = get_like_count(item["id"])
        
    items.sort(key=lambda x: x['id'], reverse=True)
    total = len(items)
    start = (page - 1) * limit
    end = start + limit
    return {"page": page, "limit": limit, "total": total, "items": items[start:end]}

def find_post(post_id: int) -> dict | None:
    return _posts.get(post_id)

def create_post(user_id: int, title: str, content: str, image_url: str = None) -> dict:
    global _post_seq
    post = {
        "id": _post_seq,
        "user_id": user_id,
        "title": title,
        "content": content,
        "image_url": image_url,
        "views": 0
    }
    _posts[_post_seq] = post
    _post_seq += 1
    return post

def update_post(post_id: int, title: str, content: str, image_url: str = None) -> dict:
    post = _posts.get(post_id)
    if post:
        post["title"] = title
        post["content"] = content
        if image_url is not None:
            post["image_url"] = image_url
    return post

def delete_post(post_id: int):
    _posts.pop(post_id, None)

# --- 좋아요 로직 ---
def add_like(user_id: int, post_id: int):
    _likes.add((user_id, post_id))

def remove_like(user_id: int, post_id: int):
    _likes.discard((user_id, post_id))

def get_like_count(post_id: int) -> int:
    return sum(1 for uid, pid in _likes if pid == post_id)