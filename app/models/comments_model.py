from __future__ import annotations

from typing import Dict, List, Optional

_comments: Dict[int, dict] = {}
_comment_seq: int = 1


def create_comment(post_id: int, author_id: int, content: str) -> dict:
    global _comment_seq
    comment = {
        "id": _comment_seq,
        "post_id": post_id,
        "author_id": author_id,
        "content": content,
    }
    _comments[_comment_seq] = comment
    _comment_seq += 1
    return comment


def list_comments(post_id: int) -> List[dict]:
    return [c for c in _comments.values() if c["post_id"] == post_id]


def delete_comment(comment_id: int) -> bool:
    return _comments.pop(comment_id, None) is not None


def find_comment_by_id(comment_id: int) -> Optional[dict]:
    return _comments.get(comment_id)
