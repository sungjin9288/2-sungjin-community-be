from typing import Optional

# users_model import 필요
from app.models import users_model

_posts: dict[int, dict] = {}
_post_seq: int = 1

# 좋아요 저장소 (user_id, post_id) 조합으로 중복 방지
_likes: set[tuple[int, int]] = set()


def list_posts(page: int = 1, limit: int = 10) -> dict:
    """게시글 목록 조회 (작성자 정보 포함)"""
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
        
        # ⭐ 댓글 수 추가
        from app.models import comments_model
        d["comments_count"] = comments_model.get_comment_count(d["id"])
        
        # ⭐ 작성자 정보 추가
        user = users_model.get_user_by_id(d["user_id"])
        if user:
            d["author_nickname"] = user.get("nickname", "Unknown")
            d["author_profile_image"] = user.get("profile_image_url")
        
        view_items.append(d)

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "items": view_items
    }


def find_post(post_id: int) -> Optional[dict]:
    """게시글 상세 조회"""
    post = _posts.get(post_id)
    if not post:
        return None
    
    # ⭐ 작성자 정보 추가
    result = post.copy()
    
    # ⭐ 댓글 수 추가
    from app.models import comments_model
    result["comments_count"] = comments_model.get_comment_count(post_id)
    
    user = users_model.get_user_by_id(result["user_id"])
    if user:
        result["author_nickname"] = user.get("nickname", "Unknown")
        result["author_profile_image"] = user.get("profile_image_url")
    
    return result


def create_post(
    user_id: int,
    title: str,
    content: str,
    image_url: Optional[str] = None
) -> dict:
    """게시글 생성"""
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
    
    # ⭐ 작성자 정보 추가
    result = post.copy()
    user = users_model.get_user_by_id(user_id)
    if user:
        result["author_nickname"] = user.get("nickname", "Unknown")
        result["author_profile_image"] = user.get("profile_image_url")
    
    return result


def update_post(
    post_id: int,
    title: str,
    content: str,
    image_url: Optional[str] = None
) -> Optional[dict]:
    """게시글 수정"""
    post = _posts.get(post_id)
    if not post:
        return None
    
    post["title"] = title
    post["content"] = content
    if image_url is not None:
        post["image_url"] = image_url
    
    # ⭐ 작성자 정보 추가
    result = post.copy()
    user = users_model.get_user_by_id(result["user_id"])
    if user:
        result["author_nickname"] = user.get("nickname", "Unknown")
        result["author_profile_image"] = user.get("profile_image_url")
    
    return result


def delete_post(post_id: int) -> None:
    """게시글 삭제"""
    _posts.pop(post_id, None)
    
    # 연관된 좋아요 삭제
    to_remove = [(uid, pid) for (uid, pid) in _likes if pid == post_id]
    for t in to_remove:
        _likes.discard(t)


def increment_views(post_id: int) -> None:
    """조회수 증가"""
    post = _posts.get(post_id)
    if post:
        post["views"] += 1


# ==================== 좋아요 관리 ====================

def add_like(user_id: int, post_id: int) -> None:
    """좋아요 추가"""
    _likes.add((user_id, post_id))


def remove_like(user_id: int, post_id: int) -> None:
    """좋아요 제거"""
    _likes.discard((user_id, post_id))


def is_liked(user_id: int, post_id: int) -> bool:
    """좋아요 여부 확인"""
    return (user_id, post_id) in _likes


def get_like_count(post_id: int) -> int:
    """좋아요 수 조회"""
    return sum(1 for _, pid in _likes if pid == post_id)