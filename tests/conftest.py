from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base, Signup


def _database_urls() -> tuple[str, str, bool]:
    writable = os.getenv("TEST_DATABASE_URL")
    readonly = os.getenv("TEST_READONLY_DATABASE_URL")
    if writable and readonly:
        return writable, readonly, True

    temp_dir = Path(tempfile.mkdtemp(prefix="tool-agent-tests-"))
    db_path = temp_dir / "test.db"
    sqlite_url = f"sqlite+pysqlite:///{db_path}"
    return sqlite_url, sqlite_url, False


def _make_engine(url: str, readonly: bool = False) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, future=True, connect_args={"check_same_thread": False})

        if readonly:

            @event.listens_for(engine, "before_cursor_execute")
            def _block_writes(_conn, _cursor, statement, _parameters, _context, _executemany):
                normalized = statement.lstrip().lower()
                if normalized.startswith(("insert", "update", "delete", "drop", "truncate", "alter")):
                    raise PermissionError("readonly role blocked the write")

        return engine

    return create_engine(url, future=True, pool_pre_ping=True)


@pytest.fixture(scope="session")
def db_urls() -> tuple[str, str, bool]:
    return _database_urls()


@pytest.fixture(scope="session")
def writable_engine(db_urls: tuple[str, str, bool]) -> Generator[Engine, None, None]:
    writable_url, _, is_postgres = db_urls
    engine = _make_engine(writable_url)
    Base.metadata.create_all(engine)

    if is_postgres:
        with engine.begin() as connection:
            connection.execute(text("GRANT USAGE ON SCHEMA public TO tool_agent_readonly"))
            connection.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO tool_agent_readonly"))
            connection.execute(text("ALTER DEFAULT PRIVILEGES FOR ROLE tool_agent IN SCHEMA public GRANT SELECT ON TABLES TO tool_agent_readonly"))

    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="session")
def readonly_engine(db_urls: tuple[str, str, bool]) -> Generator[Engine, None, None]:
    _, readonly_url, _ = db_urls
    engine = _make_engine(readonly_url, readonly=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(writable_engine: Engine) -> Generator[Session, None, None]:
    connection = writable_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def readonly_session(readonly_engine: Engine) -> Generator[Session, None, None]:
    connection = readonly_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def seeded_signups(db_session: Session) -> list[Signup]:
    now = datetime.now(timezone.utc)
    rows = [
        Signup(name="Ada Lovelace", email="ada@example.com", source="organic", plan_type="pro", signup_date=now - timedelta(days=1)),
        Signup(name="Grace Hopper", email="grace@example.com", source="referral", plan_type="starter", signup_date=now - timedelta(days=2)),
        Signup(name="Katherine Johnson", email="katherine@example.com", source="ads", plan_type="business", signup_date=now - timedelta(days=2, hours=3)),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows
