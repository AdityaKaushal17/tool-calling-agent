from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, select

from app.db.models import Signup
from app.db.session import SessionLocal, init_db


def summarize(limit: int) -> dict[str, object]:
    with SessionLocal() as db:
        total_rows = db.execute(select(func.count(Signup.id))).scalar_one()
        source_rows = db.execute(select(Signup.source, func.count(Signup.id)).group_by(Signup.source)).all()
        plan_rows = db.execute(select(Signup.plan_type, func.count(Signup.id)).group_by(Signup.plan_type)).all()
        latest_rows = db.execute(select(Signup).order_by(Signup.signup_date.desc()).limit(limit)).scalars().all()

    return {
        "total_rows": int(total_rows or 0),
        "source_counts": {source: int(count) for source, count in source_rows},
        "plan_counts": {plan: int(count) for plan, count in plan_rows},
        "latest_rows": [
            {
                "name": row.name,
                "email": row.email,
                "source": row.source,
                "plan_type": row.plan_type,
                "signup_date": row.signup_date.isoformat(),
            }
            for row in latest_rows
        ],
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect seeded signup data in the local database.")
    parser.add_argument("--limit", type=int, default=10, help="How many recent rows to print")
    parser.add_argument("--init-db", action="store_true", help="Create tables before inspecting")
    args = parser.parse_args()

    if args.init_db:
        init_db()

    print(json.dumps(summarize(args.limit), indent=2))


if __name__ == "__main__":
    main()
