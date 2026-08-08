from dataclasses import dataclass
from email.message import EmailMessage
import smtplib

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.config import get_settings


class SignupEmailPayload(BaseModel):
    recipient_email: EmailStr
    team_name: str = Field(min_length=1)
    date_range: str = Field(min_length=1)
    signup_count: int = Field(ge=0)
    top_source: str = Field(min_length=1)
    source_breakdown: dict[str, int]

    @field_validator("source_breakdown")
    @classmethod
    def ensure_non_negative(cls, value: dict[str, int]) -> dict[str, int]:
        if any(count < 0 for count in value.values()):
            raise ValueError("source breakdown cannot contain negative counts")
        return value


@dataclass(frozen=True)
class EmailDeliveryResult:
    sent: bool
    provider_message_id: str | None
    subject: str
    body: str


def render_signup_summary_email(payload: SignupEmailPayload) -> tuple[str, str]:
    subject = f"{payload.team_name.title()} signups summary for {payload.date_range}"
    breakdown_lines = "\n".join(f"- {source}: {count}" for source, count in sorted(payload.source_breakdown.items())) or "- No signups found"
    body = (
        f"Hello {payload.team_name.title()} team,\n\n"
        f"Here is the signup summary for {payload.date_range}:\n"
        f"Total signups: {payload.signup_count}\n"
        f"Top source: {payload.top_source}\n\n"
        f"Source breakdown:\n{breakdown_lines}\n\n"
        "This message is generated from database-backed data only."
    )
    return subject, body


def send_signup_summary_email(payload: SignupEmailPayload) -> EmailDeliveryResult:
    settings = get_settings()
    subject, body = render_signup_summary_email(payload)

    message = EmailMessage()
    message["From"] = str(settings.email_from)
    message["To"] = str(payload.recipient_email)
    message["Subject"] = subject
    message.set_content(body)

    if not settings.smtp_host:
        return EmailDeliveryResult(sent=False, provider_message_id=None, subject=subject, body=body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        response = smtp.send_message(message)

    return EmailDeliveryResult(sent=True, provider_message_id=str(response) if response else None, subject=subject, body=body)
