
from typing import Optional


_comments: dict[int, dict] = {}
_comment_seq: int = 1


def list_comments(post_id: int) -> list[dict]:

    return [c for c in _comments.values() if c["post_id"] == post_id]


def find_comment(comment_id: int) -> Optional[dict]:

    return _comments.get(comment_id)


def create_comment(user_id: int, post_id: int, content: str) -> dict:

    global _comment_seq
    comment = {
        "id": _comment_seq,
        "user_id": user_id,
        "post_id": post_id,
        "content": content
    }
    _comments[_comment_seq] = comment
    _comment_seq += 1
    return comment


def delete_comment(comment_id: int) -> None:

    _comments.pop(comment_id, None)