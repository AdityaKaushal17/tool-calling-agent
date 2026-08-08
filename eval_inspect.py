from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def load_signups(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def summarize(rows: list[dict]) -> dict[str, object]:
    source_counts = Counter(row["source"] for row in rows)
    plan_counts = Counter(row["plan_type"] for row in rows)
    return {
        "rows": len(rows),
        "source_counts": dict(source_counts),
        "plan_counts": dict(plan_counts),
        "sample": rows[:5],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a JSON export of seeded signups.")
    parser.add_argument("path", type=Path, help="Path to a JSON file of signups")
    args = parser.parse_args()

    rows = load_signups(args.path)
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()
