from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import re
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agent.guardrails import detect_destructive_intent, detect_hallucination_intent, validate_grounded_email
from app.agent.tools.db_query_tool import SignupSummaryRequest, get_signup_summary
from app.agent.tools.email_tool import SignupEmailPayload, render_signup_summary_email, send_signup_summary_email
from app.core.config import get_settings
from app.db.audit import create_audit_entry, finalize_audit_entry
from app.db.readonly_session import ReadOnlySessionLocal
from app.db.session import SessionLocal


class AgentState(TypedDict, total=False):
    task_id: str
    user_id: int
    user_email: str
    request_text: str
    blocked: bool
    blocked_reason: str
    start_date: date
    end_date: date
    report: dict
    email_payload: dict
    email_result: dict
    result: dict


_LAST_N_DAYS = re.compile(r"\b(?:last|past)\s+(\d{1,3})\s+days?\b")


def _resolve_window(request_text: str, today: date | None = None) -> tuple[date, date]:
    today = today or datetime.now(timezone.utc).date()
    text = request_text.lower()

    if "last week" in text:
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=6)
    if "this week" in text:
        return today - timedelta(days=today.weekday()), today
    if "yesterday" in text:
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if "today" in text:
        return today, today
    match = _LAST_N_DAYS.search(text)
    if match:
        days = max(1, min(int(match.group(1)), 365))
        return today - timedelta(days=days), today
    return today - timedelta(days=7), today


def _resolve_team_email(request_text: str) -> str:
    settings = get_settings()
    if re.search(r"\bsales\b", request_text, flags=re.IGNORECASE):
        return str(settings.sales_team_email)
    return str(settings.sales_team_email)


@contextmanager
def _audited(session_factory, *, task_id: str, user_id: int, action: str, input_json: dict):
    """Record a tool call in audit_log. The 'started' row is committed up front,
    and the outcome is written in a fresh transaction so a failure inside the
    tool (or a bad payload) can never poison the audit session."""
    with session_factory() as audit_db:
        entry = create_audit_entry(audit_db, task_id=task_id, user_id=user_id, action=action, input_json=input_json)
        audit_db.commit()
        outcome: dict = {}
        try:
            yield outcome
        except Exception as exc:
            audit_db.rollback()
            finalize_audit_entry(audit_db, entry, output_json={"error": str(exc)}, status="failed")
            audit_db.commit()
            raise
        finalize_audit_entry(audit_db, entry, output_json=outcome.get("output"), status="succeeded")
        audit_db.commit()


def build_agent_graph(*, session_factory=None, readonly_session_factory=None):
    """session factories are injectable so tests and the eval harness can run the
    real graph against a throwaway database; production uses the configured ones."""
    session_factory = session_factory or SessionLocal
    readonly_session_factory = readonly_session_factory or ReadOnlySessionLocal
    builder = StateGraph(AgentState)

    def guardrails_node(state: AgentState) -> AgentState:
        intent = detect_destructive_intent(state["request_text"])
        if not intent.allowed:
            return {"blocked": True, "blocked_reason": intent.reason or "request blocked"}

        hallucination_intent = detect_hallucination_intent(state["request_text"])
        if not hallucination_intent.allowed:
            return {"blocked": True, "blocked_reason": hallucination_intent.reason or "request blocked"}

        start_date, end_date = _resolve_window(state["request_text"])
        return {"start_date": start_date, "end_date": end_date}

    def query_node(state: AgentState) -> AgentState:
        request = SignupSummaryRequest(start_date=state["start_date"], end_date=state["end_date"])

        with _audited(
            session_factory,
            task_id=state["task_id"],
            user_id=state["user_id"],
            action="db_query_tool.get_signup_summary",
            input_json={"start_date": request.start_date.isoformat(), "end_date": request.end_date.isoformat()},
        ) as outcome:
            with readonly_session_factory() as db:
                summary = get_signup_summary(db, request)
            outcome["output"] = summary.to_json()

        return {"report": summary.to_json()}

    def compose_email_node(state: AgentState) -> AgentState:
        report = state["report"]
        payload = SignupEmailPayload(
            recipient_email=_resolve_team_email(state["request_text"]),
            team_name="sales",
            date_range=f"{report['start_date']} to {report['end_date']}",
            signup_count=report["signup_count"],
            top_source=report["top_source"],
            source_breakdown=report["source_breakdown"],
        )

        _subject, body = render_signup_summary_email(payload)
        grounded = validate_grounded_email(body, report)
        if not grounded.allowed:
            return {"blocked": True, "blocked_reason": grounded.reason or "grounding check failed"}

        return {"email_payload": payload.model_dump(mode="json")}

    def email_node(state: AgentState) -> AgentState:
        payload = SignupEmailPayload.model_validate(state["email_payload"])

        with _audited(
            session_factory,
            task_id=state["task_id"],
            user_id=state["user_id"],
            action="email_tool.send_signup_summary_email",
            input_json=payload.model_dump(mode="json"),
        ) as outcome:
            result = send_signup_summary_email(payload)
            outcome["output"] = asdict(result)

        return {"email_result": asdict(result)}

    def finalize_node(state: AgentState) -> AgentState:
        if state.get("blocked"):
            return {"result": {"status": "blocked", "reason": state.get("blocked_reason", "blocked")}}
        return {
            "result": {
                "status": "completed",
                "report": state.get("report"),
                "email_result": state.get("email_result"),
            }
        }

    builder.add_node("guardrails", guardrails_node)
    builder.add_node("query", query_node)
    builder.add_node("compose_email", compose_email_node)
    builder.add_node("send_email", email_node)
    builder.add_node("finalize", finalize_node)

    builder.set_entry_point("guardrails")
    builder.add_conditional_edges(
        "guardrails",
        lambda state: "finalize" if state.get("blocked") else "query",
        {"query": "query", "finalize": "finalize"},
    )
    builder.add_edge("query", "compose_email")
    builder.add_conditional_edges(
        "compose_email",
        lambda state: "finalize" if state.get("blocked") else "send_email",
        {"send_email": "send_email", "finalize": "finalize"},
    )
    builder.add_edge("send_email", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()


def run_agent_request(*, task_id: str, user_id: int, user_email: str, request_text: str, **factories) -> dict:
    graph = build_agent_graph(**factories)
    state = graph.invoke({"task_id": task_id, "user_id": user_id, "user_email": user_email, "request_text": request_text})
    return state.get("result", {"status": "failed"})
