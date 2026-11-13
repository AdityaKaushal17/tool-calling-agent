from __future__ import annotations

import logging
from datetime import datetime, timezone

from redis import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.readonly_session import ReadOnlySessionLocal
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def _ping_database(session_factory) -> None:
    with session_factory() as db:
        db.execute(text("SELECT 1"))


def _ping_redis() -> None:
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    redis_client.ping()


def verify_startup_dependencies() -> None:
    _ping_database(SessionLocal)
    _ping_database(ReadOnlySessionLocal)
    _verify_readonly_role_cannot_write()
    _ping_redis()


def _verify_readonly_role_cannot_write() -> None:
    probe = text(
        "INSERT INTO signups (name, email, source, plan_type, signup_date) VALUES (:name, :email, :source, :plan_type, :signup_date)"
    )
    payload = {
        "name": "Readonly Probe",
        "email": "readonly-probe@example.com",
        "source": "organic",
        "plan_type": "free",
        "signup_date": datetime.now(timezone.utc),
    }

    try:
        with ReadOnlySessionLocal() as db:
            db.execute(probe, payload)
            db.rollback()
    except Exception:
        return

    raise RuntimeError("read-only database role accepted a write")


def check_service_health() -> dict[str, str]:
    health = {"postgres": "ok", "readonly_postgres": "ok", "redis": "ok"}

    try:
        _ping_database(SessionLocal)
    except Exception:
        # Detail goes to logs only: raw errors can leak hostnames/usernames to anonymous callers.
        logger.exception("health check failed: postgres")
        health["postgres"] = "error"

    try:
        _ping_database(ReadOnlySessionLocal)
    except Exception:
        # Detail goes to logs only: raw errors can leak hostnames/usernames to anonymous callers.
        logger.exception("health check failed: readonly_postgres")
        health["readonly_postgres"] = "error"

    try:
        _ping_redis()
    except Exception:
        # Detail goes to logs only: raw errors can leak hostnames/usernames to anonymous callers.
        logger.exception("health check failed: redis")
        health["redis"] = "error"

    return health