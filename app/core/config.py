from functools import lru_cache

from pydantic import EmailStr, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "tool-agent"
    environment: str = "development"
    secret_key: SecretStr = Field(default=SecretStr("change-me"))
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    database_url: str = "postgresql+psycopg://tool_agent:tool_agent@postgres:5432/tool_agent"
    readonly_database_url: str = "postgresql+psycopg://tool_agent_readonly:tool_agent_readonly@postgres:5432/tool_agent"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"
    rate_limit_per_hour: int = 10
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_use_tls: bool = True
    email_from: EmailStr = "no-reply@example.com"
    sales_team_email: EmailStr = "sales@example.com"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
