from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ★ 변경된 부분: mysql+pymysql 사용, 포트 3306
# 형식: mysql+pymysql://아이디:비밀번호@주소:포트/데이터베이스이름
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:start21@localhost:3306/community_db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()