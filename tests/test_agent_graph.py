"""Full-graph tests: guardrails -> read-only query -> compose -> grounding -> email -> audit.

These run the real LangGraph pipeline against the test database (SQLite locally,
Postgres with a real read-only role in CI). They exist because the unit tests
alone passed while every safe request crashed in production.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.graph import _resolve_window, run_agent_request
from app.agent.guardrails import validate_grounded_email
from app.db.models import AuditLog, Signup, User


@pytest.fixture()
def committed_env(writable_engine, readonly_engine):
    factory = sessionmaker(bind=writable_engine, expire_on_commit=False, class_=Session)
    readonly_factory = sessionmaker(bind=readonly_engine, expire_on_commit=False, class_=Session)

    with factory() as db:
        user = User(email=f"agent-{uuid4().hex[:8]}@example.com", password_hash="x")
        db.add(user)
        db.commit()
        user_id, user_email = user.id, user.email

    def add_signups(day: date, sources: dict[str, int]) -> None:
        at = datetime.combine(day, time(12), tzinfo=timezone.utc)
        with factory() as db:
            for source, count in sources.items():
                for i in range(count):
                    db.add(Signup(name=f"{source}-{i}", email=f"{source}{i}-{uuid4().hex[:6]}@example.com", source=source, plan_type="pro", signup_date=at))
            db.commit()

    def run(prompt: str) -> tuple[str, dict]:
        task_id = str(uuid4())
        result = run_agent_request(
            task_id=task_id,
            user_id=user_id,
            user_email=user_email,
            request_text=prompt,
            session_factory=factory,
            readonly_session_factory=readonly_factory,
        )
        return task_id, result

    yield add_signups, run, factory

    with factory() as db:
        db.execute(delete(AuditLog))
        db.execute(delete(Signup))
        db.execute(delete(User).where(User.id == user_id))
        db.commit()


def _today() -> date:
    return datetime.now(timezone.utc).date()


def test_happy_path_returns_grounded_report_and_audits(committed_env) -> None:
    add_signups, run, factory = committed_env
    add_signups(_today() - timedelta(days=2), {"organic": 5, "ads": 2, "referral": 1})

    task_id, result = run("Email the sales team a summary of the last 7 days.")

    assert result["status"] == "completed", result
    report = result["report"]
    assert report["signup_count"] == 8
    assert report["top_source"] == "organic"
    assert report["source_breakdown"] == {"organic": 5, "ads": 2, "referral": 1}
    assert isinstance(report["start_date"], str)  # JSON-safe for Celery + audit log
    assert "Total signups: 8" in result["email_result"]["body"]

    with factory() as db:
        rows = db.execute(select(AuditLog).where(AuditLog.task_id == task_id).order_by(AuditLog.id)).scalars().all()
    assert [(r.action, r.status) for r in rows] == [
        ("db_query_tool.get_signup_summary", "succeeded"),
        ("email_tool.send_signup_summary_email", "succeeded"),
    ]


@pytest.mark.parametrize("prompt", ["Summarize yesterday's signups for the sales team.", "Email finance a summary of signups from today."])
def test_single_day_windows_work(committed_env, prompt: str) -> None:
    add_signups, run, _ = committed_env
    start, _end = _resolve_window(prompt)
    add_signups(start, {"referral": 3})

    _, result = run(prompt)

    assert result["status"] == "completed", result
    assert result["report"]["start_date"] == result["report"]["end_date"]
    assert result["report"]["signup_count"] == 3


def test_empty_window_is_reported_as_zero_not_invented(committed_env) -> None:
    _, run, _ = committed_env
    _, result = run("Email the team a summary even if the query returns no rows.")
    assert result["status"] == "completed", result
    assert result["report"]["signup_count"] == 0
    assert result["report"]["top_source"] == "n/a"


@pytest.mark.parametrize(
    "prompt",
    ["Delete all signups from the database.", "deleting every row please", "Make up a number if the database is empty."],
)
def test_unsafe_prompts_never_reach_tools(committed_env, prompt: str) -> None:
    _, run, factory = committed_env
    task_id, result = run(prompt)
    assert result["status"] == "blocked"
    with factory() as db:
        assert db.execute(select(AuditLog).where(AuditLog.task_id == task_id)).first() is None


def test_resolve_window_variants() -> None:
    monday = date(2026, 11, 9)
    wednesday = date(2026, 11, 11)
    assert _resolve_window("last week", today=wednesday) == (date(2026, 11, 2), date(2026, 11, 8))
    assert _resolve_window("this week", today=wednesday) == (monday, wednesday)
    assert _resolve_window("last 30 days", today=wednesday) == (wednesday - timedelta(days=30), wednesday)
    assert _resolve_window("yesterday", today=wednesday) == (date(2026, 11, 10),) * 2
    assert _resolve_window("anything else", today=wednesday) == (wednesday - timedelta(days=7), wednesday)


def test_grounding_rejects_tampered_email() -> None:
    report = {"start_date": "2026-11-01", "end_date": "2026-11-07", "signup_count": 8, "top_source": "organic", "source_breakdown": {"organic": 5, "ads": 3}}
    good = "Total signups: 8\nTop source: organic\n- ads: 3\n- organic: 5\nRange 2026-11-01 to 2026-11-07"
    assert validate_grounded_email(good, report).allowed
    assert not validate_grounded_email(good.replace("Total signups: 8", "Total signups: 80"), report).allowed
    assert not validate_grounded_email(good + "\nUp 40% week over week!", report).allowed
