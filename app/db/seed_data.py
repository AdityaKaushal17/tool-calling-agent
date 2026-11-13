import random
from datetime import datetime, timedelta, timezone

from faker import Faker

from app.db.models import Signup

SOURCES = ["organic", "referral", "ads", "social", "partner", "newsletter"]
PLANS = ["free", "starter", "pro", "business", "enterprise"]


def generate_rows(total_rows: int, days: int = 60) -> list[Signup]:
    fake = Faker()
    now = datetime.now(timezone.utc)
    return [
        Signup(
            name=fake.name(),
            email=fake.unique.email(),
            source=random.choice(SOURCES),
            plan_type=random.choice(PLANS),
            signup_date=now - timedelta(days=random.randint(0, days - 1), hours=random.randint(0, 23), minutes=random.randint(0, 59)),
        )
        for _ in range(total_rows)
    ]
