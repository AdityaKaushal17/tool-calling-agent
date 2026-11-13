from functools import lru_cache

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator
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
    # Default to REDIS_URL so a single managed Redis/Key Value instance is enough in production.
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    rate_limit_per_hour: int = 10
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_use_tls: bool = True
    email_from: EmailStr = "no-reply@example.com"
    sales_team_email: EmailStr = "sales@example.com"
    seed_if_empty: int = 0

    @field_validator("database_url", "readonly_database_url")
    @classmethod
    def use_psycopg3_driver(cls, value: str) -> str:
        # Neon/Render hand out postgres:// or postgresql:// URLs, which SQLAlchemy maps to
        # psycopg2 (not installed). Pin the psycopg 3 driver we actually ship.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @model_validator(mode="after")
    def fill_celery_urls(self) -> "Settings":
        self.celery_broker_url = self.celery_broker_url or self.redis_url
        self.celery_result_backend = self.celery_result_backend or self.redis_url
        return self

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
