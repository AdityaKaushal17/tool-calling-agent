import re
from dataclasses import dataclass


DESTRUCTIVE_PATTERN = re.compile(r"\b(delete|update|drop|truncate|alter|insert|merge|purge|wipe|erase|clear|remove everything|remove all|clear out)\b", re.IGNORECASE)
HALLUCINATION_PATTERN = re.compile(r"\b(make up|invent|hallucinate|guess|estimate|round up|assume the usual amount|assume usual amount|without querying|do not query|ignore the database|make the numbers look good|make it look good|if you're not sure|if you are not sure)\b", re.IGNORECASE)


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str | None = None


def detect_destructive_intent(text: str) -> GuardrailResult:
    if DESTRUCTIVE_PATTERN.search(text):
        return GuardrailResult(allowed=False, reason="destructive intent detected")
    return GuardrailResult(allowed=True)


def detect_hallucination_intent(text: str) -> GuardrailResult:
    if HALLUCINATION_PATTERN.search(text):
        return GuardrailResult(allowed=False, reason="hallucination intent detected")
    return GuardrailResult(allowed=True)


def validate_grounded_summary(expected_count: int, expected_top_source: str, actual_count: int, actual_top_source: str) -> GuardrailResult:
    if expected_count != actual_count or expected_top_source != actual_top_source:
        return GuardrailResult(allowed=False, reason="summary does not match database facts")
    return GuardrailResult(allowed=True)
