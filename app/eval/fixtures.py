from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalFixture:
    prompt: str
    blocked: bool
    signup_count: int
    top_source: str
    source_breakdown: dict[str, int]


def fixture_snapshot(item: dict) -> dict[str, object]:
    fixture = item["fixture"]
    return {
        "signup_count": fixture["signup_count"],
        "top_source": fixture["top_source"],
        "source_breakdown": fixture["source_breakdown"],
        "date_range": item.get("date_range", "2026-08-01 to 2026-08-07"),
    }
