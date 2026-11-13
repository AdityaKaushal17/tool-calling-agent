import re
from dataclasses import dataclass


# Verb stems so inflections ("deleting", "dropped", "wiped") can't slip past.
# "update" is only treated as destructive when used as a verb ("an update on X" is fine);
# "clear" only when it targets data ("clear out", "clear all", "clear the ...").
DESTRUCTIVE_PATTERN = re.compile(
    r"\b("
    r"delet(?:e|es|ed|ing)"
    r"|(?<!\ban )(?<!\bthe )updat(?:e|es|ed|ing)"
    r"|drop(?:s|ped|ping)?"
    r"|truncat(?:e|es|ed|ing)"
    r"|alter(?:s|ed|ing)?"
    r"|insert(?:s|ed|ing)?"
    r"|merg(?:e|es|ed|ing)"
    r"|purg(?:e|es|ed|ing)"
    r"|wip(?:e|es|ed|ing)"
    r"|eras(?:e|es|ed|ing)"
    r"|destroy(?:s|ed|ing)?"
    r"|overwrit(?:e|es|ing)|overwritten"
    r"|clear(?:s|ed|ing)?\s+(?:out|all|everything|the|every)"
    r"|remov(?:e|es|ed|ing)\s+(?:everything|all|every)"
    r")\b",
    re.IGNORECASE,
)
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


def validate_grounded_email(body: str, report: dict) -> GuardrailResult:
    """Check the *rendered* email against the database report: the total, the top
    source and every per-source line must match, and no other numbers may appear."""
    expected_lines = {
        f"Total signups: {report['signup_count']}",
        f"Top source: {report['top_source']}",
        *(f"- {source}: {count}" for source, count in report["source_breakdown"].items()),
    }
    missing = [line for line in expected_lines if line not in body.splitlines()]
    if missing:
        return GuardrailResult(allowed=False, reason=f"email missing database facts: {missing}")

    allowed_numbers = {str(report["signup_count"]), *(str(c) for c in report["source_breakdown"].values())}
    for date_part in (report.get("start_date", ""), report.get("end_date", "")):
        allowed_numbers.update(re.findall(r"\d+", date_part))
    stray = sorted(set(re.findall(r"\d+", body)) - allowed_numbers)
    if stray:
        return GuardrailResult(allowed=False, reason=f"email contains numbers not in database result: {stray}")
    return GuardrailResult(allowed=True)


def validate_grounded_summary(expected_count: int, expected_top_source: str, actual_count: int, actual_top_source: str) -> GuardrailResult:
    if expected_count != actual_count or expected_top_source != actual_top_source:
        return GuardrailResult(allowed=False, reason="summary does not match database facts")
    return GuardrailResult(allowed=True)
