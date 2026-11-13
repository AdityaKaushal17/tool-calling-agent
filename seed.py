from __future__ import annotations

import argparse
from sqlalchemy import delete

from app.db.models import Signup
from app.db.seed_data import generate_rows
from app.db.session import SessionLocal, init_db


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
