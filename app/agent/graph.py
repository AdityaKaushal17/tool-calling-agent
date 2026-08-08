from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import re
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agent.guardrails import detect_destructive_intent, detect_hallucination_intent, validate_grounded_summary
from app.agent.tools.db_query_tool import SignupSummaryRequest, get_signup_summary
from app.agent.tools.email_tool import SignupEmailPayload, send_signup_summary_email
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


def _resolve_window(request_text: str) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    text = request_text.lower()

    if "last week" in text:
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start, end
    if "yesterday" in text:
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if "today" in text:
        return today, today
    if "last 7 days" in text:
        return today - timedelta(days=7), today
    return today - timedelta(days=7), today


def _resolve_team_email(request_text: str) -> str:
    settings = get_settings()
    if re.search(r"\bsales\b", request_text, flags=re.IGNORECASE):
        return str(settings.sales_team_email)
    return str(settings.sales_team_email)


def build_agent_graph():
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

        with SessionLocal() as audit_db:
            audit_entry = create_audit_entry(
                audit_db,
                task_id=state["task_id"],
                user_id=state["user_id"],
                action="db_query_tool.get_signup_summary",
                input_json={"start_date": request.start_date.isoformat(), "end_date": request.end_date.isoformat()},
            )
            try:
                with ReadOnlySessionLocal() as db:
                    summary = get_signup_summary(db, request)
                finalize_audit_entry(audit_db, audit_entry, output_json=asdict(summary), status="succeeded")
                audit_db.commit()
            except Exception as exc:
                finalize_audit_entry(audit_db, audit_entry, output_json={"error": str(exc)}, status="failed")
                audit_db.commit()
                raise

        return {"report": asdict(summary)}

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

        grounded = validate_grounded_summary(
            expected_count=report["signup_count"],
            expected_top_source=report["top_source"],
            actual_count=payload.signup_count,
            actual_top_source=payload.top_source,
        )
        if not grounded.allowed:
            return {"blocked": True, "blocked_reason": grounded.reason or "grounding check failed"}

        return {"email_payload": payload.model_dump()}

    def email_node(state: AgentState) -> AgentState:
        payload = SignupEmailPayload.model_validate(state["email_payload"])

        with SessionLocal() as audit_db:
            audit_entry = create_audit_entry(
                audit_db,
                task_id=state["task_id"],
                user_id=state["user_id"],
                action="email_tool.send_signup_summary_email",
                input_json=payload.model_dump(),
            )
            try:
                result = send_signup_summary_email(payload)
                finalize_audit_entry(audit_db, audit_entry, output_json=result.__dict__, status="succeeded")
                audit_db.commit()
            except Exception as exc:
                finalize_audit_entry(audit_db, audit_entry, output_json={"error": str(exc)}, status="failed")
                audit_db.commit()
                raise

        return {"email_result": result.__dict__}

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


def run_agent_request(*, task_id: str, user_id: int, user_email: str, request_text: str) -> dict:
    graph = build_agent_graph()
    state = graph.invoke({"task_id": task_id, "user_id": user_id, "user_email": user_email, "request_text": request_text})
    return state.get("result", {"status": "failed"})
