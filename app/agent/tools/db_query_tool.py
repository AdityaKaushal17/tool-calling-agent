from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Signup


class SignupSummaryRequest(BaseModel):
    start_date: date = Field(...)
    end_date: date = Field(...)

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, value: date, info):
        start_date = info.data.get("start_date")
        if start_date and value <= start_date:
            raise ValueError("end_date must be after start_date")
        return value


@dataclass(frozen=True)
class SignupSummary:
    start_date: date
    end_date: date
    signup_count: int
    top_source: str
    source_breakdown: dict[str, int]


class SignupRecord(BaseModel):
    id: int
    name: str
    email: str
    source: str
    plan_type: str
    signup_date: datetime


class SignupsResponse(BaseModel):
    items: list[SignupRecord]


class SignupCountBySource(BaseModel):
    source: str
    signup_count: int


class SignupCountBySourceResponse(BaseModel):
    items: list[SignupCountBySource]


class GetSignupsRequest(BaseModel):
    start_date: date = Field(...)
    end_date: date = Field(...)

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, value: date, info):
        start_date = info.data.get("start_date")
        if start_date and value <= start_date:
            raise ValueError("end_date must be after start_date")
        return value


class GetSignupCountBySourceRequest(GetSignupsRequest):
    pass


def _start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _end_of_day(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def get_signup_summary(db: Session, request: SignupSummaryRequest) -> SignupSummary:
    window_start = _start_of_day(request.start_date)
    window_end = _end_of_day(request.end_date)

    rows = db.execute(
        select(Signup.source, func.count(Signup.id)).where(Signup.signup_date >= window_start, Signup.signup_date <= window_end).group_by(Signup.source)
    ).all()

    source_breakdown = {source: int(count) for source, count in rows}
    signup_count = sum(source_breakdown.values())
    top_source = max(source_breakdown, key=source_breakdown.get) if source_breakdown else "n/a"

    return SignupSummary(
        start_date=request.start_date,
        end_date=request.end_date,
        signup_count=signup_count,
        top_source=top_source,
        source_breakdown=source_breakdown,
    )


def get_signups(db: Session, request: GetSignupsRequest) -> SignupsResponse:
    window_start = _start_of_day(request.start_date)
    window_end = _end_of_day(request.end_date)

    rows = db.execute(
        select(Signup).where(Signup.signup_date >= window_start, Signup.signup_date <= window_end).order_by(Signup.signup_date.asc())
    ).scalars().all()

    return SignupsResponse(items=[SignupRecord.model_validate(row, from_attributes=True) for row in rows])


def get_signup_count_by_source(db: Session, request: GetSignupCountBySourceRequest) -> SignupCountBySourceResponse:
    window_start = _start_of_day(request.start_date)
    window_end = _end_of_day(request.end_date)

    rows = db.execute(
        select(Signup.source, func.count(Signup.id)).where(Signup.signup_date >= window_start, Signup.signup_date <= window_end).group_by(Signup.source)
    ).all()

    return SignupCountBySourceResponse(
        items=[SignupCountBySource(source=source, signup_count=int(count)) for source, count in rows]
    )
