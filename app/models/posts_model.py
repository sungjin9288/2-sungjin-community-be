from datetime import datetime
import logging
from app.database import SessionLocal
from app.db_models import Post, User, Like, Comment
from sqlalchemy import desc

logger = logging.getLogger(__name__)

# ★ 수정: 날짜(datetime)를 문자열로 변환하는 로직 추가
def _to_dict(obj):
    if not obj: return None
    data = {}
    for c in obj.__table__.columns:
        val = getattr(obj, c.name)
        if isinstance(val, datetime):
            val = val.isoformat()  # "2026-01-28T..." 형태로 변환
        data[c.name] = val
    return data

def list_posts(page: int = 1, limit: int = 10, current_user_id: int = None) -> list[dict]:
    db = SessionLocal()
    try:
        offset = (page - 1) * limit
        logger.info(f"게시글 목록 조회 요청: page={page}, limit={limit}, offset={offset}, user={current_user_id}")
        posts = db.query(Post).order_by(desc(Post.created_at)).offset(offset).limit(limit).all()
        
        logger.info(f"조회된 게시글 수: {len(posts)}")
        results = []
        for p in posts:
            p_dict = _to_dict(p)
            p_dict["author_nickname"] = p.owner.nickname if p.owner else "Unknown"
            p_dict["author_profile_image"] = p.owner.profile_image_url
            
            # 통계 데이터 추가
            p_dict["likes_count"] = len(p.likes)
            p_dict["comments_count"] = len(p.comments)
            # view_count는 이미 p_dict에 있음
            
            # 사용자별 상태
            if current_user_id:
                p_dict["is_author"] = (p.user_id == current_user_id)
                # 좋아요 여부 확인 (최적화 없이 loop 검색)
                p_dict["is_liked"] = any(l.user_id == current_user_id for l in p.likes)
            else:
                p_dict["is_author"] = False
                p_dict["is_liked"] = False
                
            results.append(p_dict)
        return results
    except Exception as e:
        logger.error(f"게시글 목록 조회 실패: {e}")
        raise
    finally:
        db.close()

def create_post(user_id, title, content, image_url=None) -> dict:
    db = SessionLocal()
    try:
        logger.info(f"게시글 생성 시도: user_id={user_id}, title={title}")
        new_post = Post(user_id=user_id, title=title, content=content, image_url=image_url)
        db.add(new_post)
        db.commit()
        db.refresh(new_post)
        
        logger.info(f"게시글 생성 성공: ID={new_post.id}")
        res = _to_dict(new_post)
        res["author_nickname"] = new_post.owner.nickname
        return res
    except Exception as e:
        logger.error(f"게시글 생성 실패: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def find_post(post_id: int, current_user_id: int = None) -> dict | None:
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post: return None
        
        res = _to_dict(post)
        res["author_nickname"] = post.owner.nickname
        res["author_profile_image"] = post.owner.profile_image_url
        
        # 통계 데이터 추가
        res["likes_count"] = len(post.likes)
        res["comments_count"] = len(post.comments)
        res["views"] = post.view_count  # 조회수 별도 필드로
        
        # 사용자별 상태
        if current_user_id:
            res["is_author"] = (post.user_id == current_user_id)
            res["is_liked"] = any(l.user_id == current_user_id for l in post.likes)
        else:
            res["is_author"] = False
            res["is_liked"] = False
            
        return res
    finally:
        db.close()

def update_post(post_id, title, content, image_url=None):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post: return None
        
        post.title = title
        post.content = content
        if image_url is not None:
            post.image_url = image_url
            
        db.commit()
        db.refresh(post)
        return _to_dict(post)
    except:
        db.rollback()
        raise
    finally:
        db.close()

def delete_post(post_id: int):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            db.delete(post)
            db.commit()
    except:
        db.rollback()
        raise
    finally:
        db.close()

def increment_views(post_id: int):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            post.view_count += 1
            db.commit()
    finally:
        db.close()

def get_like_count(post_id: int) -> int:
    db = SessionLocal()
    try:
        return db.query(Like).filter(Like.post_id == post_id).count()
    finally:
        db.close()

def is_liked(user_id: int, post_id: int) -> bool:
    db = SessionLocal()
    try:
        like = db.query(Like).filter(Like.user_id == user_id, Like.post_id == post_id).first()
        return like is not None
    finally:
        db.close()

def add_like(user_id: int, post_id: int):
    db = SessionLocal()
    try:
        new_like = Like(user_id=user_id, post_id=post_id)
        db.add(new_like)
        db.commit()
    except:
        db.rollback()
        raise
    finally:
        db.close()

def remove_like(user_id: int, post_id: int):
    db = SessionLocal()
    try:
        db.query(Like).filter(Like.user_id == user_id, Like.post_id == post_id).delete()
        db.commit()
    except:
        db.rollback()
        raise
    finally:
        db.close()