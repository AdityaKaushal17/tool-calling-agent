"""Idempotent production bootstrap, run on every container start.

1. Create tables as the owner role (DATABASE_URL).
2. If READONLY_DATABASE_URL uses a different user, create that role if missing and
   grant it SELECT-only access (current tables + future tables via default privileges).
3. Optionally seed demo signups when the table is empty (SEED_IF_EMPTY=<rows>).

Safe to run repeatedly. Usage: python -m app.db.bootstrap
"""

from __future__ import annotations

import logging

from psycopg import sql
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.models import Base, Signup
from app.db.seed_data import generate_rows
from app.db.session import SessionLocal, engine

logger = logging.getLogger("bootstrap")


def ensure_readonly_role() -> None:
    settings = get_settings()
    owner = make_url(settings.database_url)
    readonly = make_url(settings.readonly_database_url)
    if not owner.drivername.startswith("postgresql"):
        return
    if readonly.username == owner.username:
        logger.warning("READONLY_DATABASE_URL uses the owner role; DB-level read-only guarantee is NOT in effect")
        return

    role = sql.Identifier(readonly.username)
    with engine.connect() as conn:
        raw = conn.connection.driver_connection
        raw.autocommit = True
        with raw.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (readonly.username,))
            if cur.fetchone() is None:
                cur.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(role, sql.Literal(readonly.password)))
                logger.info("created read-only role %s", readonly.username)
            for stmt in (
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(owner.database), role),
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role),
                sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(role),
                sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {}").format(role),
                # Belt and braces: make sure nothing ever granted write access.
                sql.SQL("REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM {}").format(role),
            ):
                cur.execute(stmt)


def seed_if_empty(rows: int) -> None:
    if rows <= 0:
        return
    with SessionLocal() as db:
        if db.scalar(select(func.count(Signup.id))):
            return
        db.add_all(generate_rows(rows))
        db.commit()
        logger.info("seeded %s demo signups", rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s bootstrap %(levelname)s %(message)s")
    Base.metadata.create_all(engine)
    ensure_readonly_role()
    seed_if_empty(get_settings().seed_if_empty)
    logger.info("bootstrap complete")


if __name__ == "__main__":
    main()
