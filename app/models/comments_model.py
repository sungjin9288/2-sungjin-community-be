_comments: dict[int, dict] = {}
_comment_seq: int = 1

def list_comments(post_id: int) -> list[dict]:
    return [c for c in _comments.values() if c["post_id"] == post_id]

def find_comment(comment_id: int) -> dict | None:
    return _comments.get(comment_id)

def create_comment(user_id: int, post_id: int, content: str) -> dict:
    global _comment_seq
    c = {"id": _comment_seq, "user_id": user_id, "post_id": post_id, "content": content}
    _comments[_comment_seq] = c
    _comment_seq += 1
    return c

def delete_comment(comment_id: int):
    _comments.pop(comment_id, None)