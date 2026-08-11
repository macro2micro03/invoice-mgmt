from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from . import config


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(config.DATABASE_URL, connect_args=_connect_args(config.DATABASE_URL))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# SQLite는 기본적으로 외래키 제약을 검사하지 않는다 — Postgres(운영 배포)는 검사하므로,
# 테스트/로컬에서도 동일한 제약 위반을 재현하고 잡아낼 수 있도록 켜둔다.
if config.DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
