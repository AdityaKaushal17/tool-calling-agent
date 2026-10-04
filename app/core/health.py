from __future__ import annotations

from datetime import datetime, timezone

from redis import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.readonly_session import ReadOnlySessionLocal
from app.db.session import SessionLocal


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
    except Exception as exc:
        health["postgres"] = f"error: {exc}"

    try:
        _ping_database(ReadOnlySessionLocal)
    except Exception as exc:
        health["readonly_postgres"] = f"error: {exc}"

    try:
        _ping_redis()
    except Exception as exc:
        health["redis"] = f"error: {exc}"

    return health