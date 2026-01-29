import random
from faker import Faker
from app.database import SessionLocal, engine
from app import db_models as models # 이름 충돌 방지용 별칭
from app.common.security import hash_password
from sqlalchemy import text

# DB 테이블 생성 확인
models.Base.metadata.create_all(bind=engine)

db = SessionLocal()
fake = Faker('ko_KR') # 한국어 데이터 생성

def init_dummy_data():
    print("🚀 더미 데이터 생성을 시작합니다...")

    # 0. 기존 데이터 초기화 (충돌 방지)
    print("🧹 기존 데이터를 청소하는 중...")
    try:
        # 외래키 제약조건 때문에 순서가 중요합니다. (자식 -> 부모 순서로 삭제)
        db.query(models.Comment).delete()
        db.query(models.Like).delete()
        db.query(models.Post).delete()
        db.query(models.User).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"⚠️ 초기화 중 오류 발생 (무시하고 진행합니다): {e}")

    # 1. 유저 1,000명 생성
    print("👤 유저 1,000명 생성 중...")
    users = []
    common_password = hash_password("Test1234!") # 속도를 위해 비밀번호 해시는 미리 한 번만 계산
    
    for i in range(1, 1001):
        # 충돌 방지를 위해 순차적인 닉네임 사용 (user_1, user_2 ...)
        # 10자 제한도 안전하게 통과함
        nickname = f"user_{i}" 
        email = f"user_{i}@example.com"
        
        users.append(models.User(
            email=email,
            password=common_password,
            nickname=nickname,
            profile_image_url=fake.image_url()
        ))
    
    # Bulk Insert (속도 향상)
    db.bulk_save_objects(users)
    db.commit()
    print("✅ 유저 생성 완료!")

    # 생성된 유저 ID 가져오기
    user_ids = [u.id for u in db.query(models.User).all()]

    # 2. 게시글 50,000개 생성
    print("📝 게시글 50,000개 생성 중 (약 1~2분 소요)...")
    posts = []
    # 미리 5만개의 가짜 데이터를 만들어두지 않고 루프 안에서 생성 (메모리 절약)
    for _ in range(50000):
        posts.append(models.Post(
            user_id=random.choice(user_ids),
            title=fake.sentence()[:26], # 26자 제한
            content=fake.text(),
            view_count=random.randint(0, 10000)
        ))
        
        # 5000개마다 커밋해서 DB 부하 줄임
        if len(posts) >= 5000:
            db.bulk_save_objects(posts)
            db.commit()
            posts = []
            print(".", end="", flush=True) # 진행상황 점찍기
            
    if posts:
        db.bulk_save_objects(posts)
        db.commit()
    print("\n✅ 게시글 생성 완료!")

    # 생성된 게시글 ID 가져오기
    # (주의: 데이터가 많아서 post_ids 리스트가 꽤 큽니다)
    post_ids = [p.id for p in db.query(models.Post).all()]

    # 3. 댓글 50,000개 생성
    print("💬 댓글 50,000개 생성 중...")
    comments = []
    for _ in range(50000):
        comments.append(models.Comment(
            user_id=random.choice(user_ids),
            post_id=random.choice(post_ids),
            content=fake.sentence()
        ))

        if len(comments) >= 5000:
            db.bulk_save_objects(comments)
            db.commit()
            comments = []
            print(".", end="", flush=True)

    if comments:
        db.bulk_save_objects(comments)
        db.commit()
    print("\n✅ 댓글 생성 완료!")
    
    print("🎉 모든 더미 데이터(총 10만건 이상) 생성이 완료되었습니다!")
    db.close()

if __name__ == "__main__":
    init_dummy_data()