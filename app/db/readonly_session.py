from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()
readonly_engine = create_engine(settings.readonly_database_url, pool_pre_ping=True, future=True)
ReadOnlySessionLocal = sessionmaker(bind=readonly_engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_readonly_db() -> Generator[Session, None, None]:
    db = ReadOnlySessionLocal()
    try:
        yield db
    finally:
        db.close()
