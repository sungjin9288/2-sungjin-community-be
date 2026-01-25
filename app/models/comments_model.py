from typing import Optional
from app.models import users_model

_comments: dict[int, dict] = {}
_comment_seq: int = 1


def list_comments(post_id: int) -> list[dict]:
    """댓글 목록 조회 (작성자 정보 포함)"""
    comments = [c for c in _comments.values() if c["post_id"] == post_id]
    
    # ⭐ 작성자 정보 추가
    result = []
    for c in comments:
        comment = c.copy()
        user = users_model.get_user_by_id(c["user_id"])
        if user:
            comment["author_nickname"] = user.get("nickname", "Unknown")
            comment["author_profile_image"] = user.get("profile_image_url")
        result.append(comment)
    
    return result


def find_comment(comment_id: int) -> Optional[dict]:
    """댓글 조회"""
    return _comments.get(comment_id)


def create_comment(user_id: int, post_id: int, content: str) -> dict:
    """댓글 생성"""
    global _comment_seq
    comment = {
        "id": _comment_seq,
        "user_id": user_id,
        "post_id": post_id,
        "content": content
    }
    _comments[_comment_seq] = comment
    _comment_seq += 1
    
    # ⭐ 작성자 정보 추가
    result = comment.copy()
    user = users_model.get_user_by_id(user_id)
    if user:
        result["author_nickname"] = user.get("nickname", "Unknown")
        result["author_profile_image"] = user.get("profile_image_url")
    
    return result


def delete_comment(comment_id: int) -> None:
    """댓글 삭제"""
    _comments.pop(comment_id, None)


def get_comment_count(post_id: int) -> int:
    """게시글의 댓글 수 조회"""
    return sum(1 for c in _comments.values() if c["post_id"] == post_id)