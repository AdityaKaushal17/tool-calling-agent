from __future__ import annotations

import pytest

from app.agent.guardrails import (
    detect_destructive_intent,
    detect_hallucination_intent,
    validate_grounded_summary,
)


@pytest.mark.parametrize(
    ("prompt",),
    [
        ("delete all signups",),
        ("please remove everything from the table",),
        ("wipe the table",),
        ("clear out the records",),
        ("purge the signups table",),
    ],
)
def test_detect_destructive_intent_blocks_destructive_phrases(prompt: str) -> None:
    result = detect_destructive_intent(prompt)
    assert result.allowed is False
    assert result.reason == "destructive intent detected"


@pytest.mark.parametrize(
    ("prompt",),
    [
        ("email the sales team a summary of last week",),
        ("summarize yesterday's signups",),
        ("tell me the top source for the last 7 days",),
    ],
)
def test_detect_destructive_intent_allows_safe_phrases(prompt: str) -> None:
    result = detect_destructive_intent(prompt)
    assert result.allowed is True
    assert result.reason is None


@pytest.mark.parametrize(
    ("prompt",),
    [
        ("make up a number if the database is empty",),
        ("just estimate if you're not sure",),
        ("round up if you don't have the exact number",),
        ("assume the usual amount of signups",),
        ("ignore the database and guess",),
    ],
)
def test_detect_hallucination_intent_blocks_pressure_phrases(prompt: str) -> None:
    result = detect_hallucination_intent(prompt)
    assert result.allowed is False
    assert result.reason == "hallucination intent detected"


@pytest.mark.parametrize(
    ("prompt",),
    [
        ("email the sales team a summary of the last 7 days",),
        ("show me the signup count from yesterday",),
        ("what was the top source last week",),
    ],
)
def test_detect_hallucination_intent_allows_safe_phrases(prompt: str) -> None:
    result = detect_hallucination_intent(prompt)
    assert result.allowed is True
    assert result.reason is None


def test_validate_grounded_summary_passes_on_exact_match() -> None:
    result = validate_grounded_summary(3, "organic", 3, "organic")
    assert result.allowed is True
    assert result.reason is None


def test_validate_grounded_summary_rejects_mismatch() -> None:
    result = validate_grounded_summary(3, "organic", 4, "organic")
    assert result.allowed is False
    assert result.reason == "summary does not match database facts"
