from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone

from faker import Faker
from sqlalchemy import delete

from app.db.models import Signup
from app.db.session import SessionLocal, init_db


SOURCES = ["organic", "referral", "ads", "social", "partner", "newsletter"]
PLANS = ["free", "starter", "pro", "business", "enterprise"]


def generate_rows(total_rows: int) -> list[Signup]:
    fake = Faker()
    now = datetime.now(timezone.utc)
    rows: list[Signup] = []

    for index in range(total_rows):
        signup_date = now - timedelta(days=random.randint(0, 59), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        rows.append(
            Signup(
                name=fake.name(),
                email=fake.unique.email(),
                source=random.choice(SOURCES),
                plan_type=random.choice(PLANS),
                signup_date=signup_date,
            )
        )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the signups table with realistic synthetic data.")
    parser.add_argument("--rows", type=int, default=750, help="Number of signup rows to generate")
    parser.add_argument("--clear", action="store_true", help="Remove existing signup rows before inserting")
    args = parser.parse_args()

    init_db()

    with SessionLocal() as db:
        if args.clear:
            db.execute(delete(Signup))
            db.commit()

        rows = generate_rows(args.rows)
        db.add_all(rows)
        db.commit()

    print(f"Seeded {args.rows} signup rows")


if __name__ == "__main__":
    main()
