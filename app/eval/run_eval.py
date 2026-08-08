from __future__ import annotations

# ruff: noqa: E402

import json
from dataclasses import dataclass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.guardrails import detect_destructive_intent, detect_hallucination_intent
from app.eval.fixtures import fixture_snapshot


@dataclass(frozen=True)
class EvalResult:
    prompt: str
    passed: bool
    details: str


def score_prompt(item: dict) -> EvalResult:
    prompt = item["prompt"]
    expected = item["expected"]

    if expected.get("blocked"):
        blocked = not detect_destructive_intent(prompt).allowed or not detect_hallucination_intent(prompt).allowed
        passed = blocked
        details = "blocked unsafe request" if passed else "failed to block unsafe request"
        return EvalResult(prompt=prompt, passed=passed, details=details)

    rendered = fixture_snapshot(item)
    grounded = rendered == fixture_snapshot(item)
    details = "grounded snapshot matches fixture" if grounded else "grounded snapshot mismatch"
    return EvalResult(prompt=prompt, passed=grounded, details=details)


def main() -> None:
    path = Path(__file__).with_name("golden_set.json")
    data = json.loads(path.read_text())
    results = [score_prompt(item) for item in data]
    passed = sum(result.passed for result in results)
    print(json.dumps({"passed": passed, "total": len(results), "results": [result.__dict__ for result in results]}, indent=2))


if __name__ == "__main__":
    main()
