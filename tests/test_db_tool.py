from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.agent.tools.db_query_tool import (
    GetSignupCountBySourceRequest,
    GetSignupsRequest,
    SignupCountBySourceResponse,
    SignupsResponse,
    get_signup_count_by_source,
    get_signups,
)


def test_readonly_role_blocks_writes(readonly_session) -> None:
    with pytest.raises(Exception):
        readonly_session.execute(
            text(
                "INSERT INTO signups (name, email, source, plan_type, signup_date) VALUES (:name, :email, :source, :plan_type, :signup_date)"
            ),
            {
                "name": "Blocked User",
                "email": "blocked@example.com",
                "source": "organic",
                "plan_type": "pro",
                "signup_date": datetime.now(timezone.utc),
            },
        )


def test_select_tools_return_typed_pydantic_models(db_session, seeded_signups) -> None:
    request = GetSignupsRequest(start_date=date.today() - timedelta(days=7), end_date=date.today())
    signups_response = get_signups(db_session, request)

    assert isinstance(signups_response, SignupsResponse)
    assert len(signups_response.items) == 3
    assert signups_response.items[0].email.endswith("@example.com")
    assert signups_response.items[0].signup_date.tzinfo is not None

    counts_response = get_signup_count_by_source(db_session, GetSignupCountBySourceRequest(start_date=request.start_date, end_date=request.end_date))
    assert isinstance(counts_response, SignupCountBySourceResponse)
    assert {item.source for item in counts_response.items} == {"organic", "referral", "ads"}
    assert sum(item.signup_count for item in counts_response.items) == 3
