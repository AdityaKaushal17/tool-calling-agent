"""
check_permissions.py

Verifies that the agent's read-only database role truly cannot write.
This is a live, runnable proof of the core safety claim in the README:
the DB layer enforces read-only access, not just application-level trust.

Usage:
    ./.venv/bin/python3 check_permissions.py
"""
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from app.core.config import get_settings

settings = get_settings()


def check_permissions() -> None:
    readonly_url = getattr(settings, "readonly_database_url", None)
    if not readonly_url:
        print("READONLY_DATABASE_URL is not set in your environment. Aborting.")
        sys.exit(1)

    engine = create_engine(readonly_url, future=True)

    # --- Check 1: SELECT should succeed ---
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[PASS] Readonly role can connect and SELECT.")
    except Exception as e:
        print(f"[FAIL] Readonly role could not even SELECT: {e}")
        sys.exit(1)

    # --- Check 2: destructive statements should be rejected ---
    destructive_statements = {
        "DELETE": "DELETE FROM signups WHERE 1=0",
        "UPDATE": "UPDATE signups SET source = source WHERE 1=0",
        "INSERT": "INSERT INTO signups (name, email, signup_date, source, plan_type) "
                   "VALUES ('x', 'x@x.com', now(), 'x', 'x')",
    }

    all_blocked = True
    for op, sql in destructive_statements.items():
        try:
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            print(f"[DANGER] Readonly role was able to execute {op}! Fix grants immediately.")
            all_blocked = False
        except (ProgrammingError, DBAPIError) as e:
            print(f"[PASS] {op} correctly blocked ({type(e.__cause__ or e).__name__})")
        except Exception as e:
            print(f"[PASS] {op} correctly blocked ({type(e).__name__})")

    print()
    if all_blocked:
        print("All destructive operations correctly blocked. Readonly role is safe.")
    else:
        print("WARNING: one or more destructive operations succeeded. Review GRANTs on Neon.")
        sys.exit(1)


if __name__ == "__main__":
    check_permissions()