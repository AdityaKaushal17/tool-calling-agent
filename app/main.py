from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status

from app.api.routes_agent import router as agent_router
from app.api.routes_auth import router as auth_router
from app.core.config import get_settings
from app.core.health import check_service_health, verify_startup_dependencies
from app.db.session import init_db
from app.logging_config import configure_logging

INSECURE_SECRETS = {"change-me", "change-me-in-production", ""}


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    if settings.is_production and settings.secret_key.get_secret_value() in INSECURE_SECRETS:
        raise RuntimeError("SECRET_KEY must be set to a strong value when ENVIRONMENT=production")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_db()
        verify_startup_dependencies()
        yield

    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        lifespan=lifespan,
        description=(
            "Backend-first tool-calling agent. Register at `/auth/register`, click **Authorize** with the token, "
            "then `POST /agent/run` with a message like *Email the sales team a summary of last week's signups* "
            "and poll `GET /agent/status/{task_id}`. Destructive or fabricate-the-numbers requests are blocked."
        ),
    )

    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(agent_router, prefix="/agent", tags=["agent"])

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        service_health = check_service_health()
        if any(value != "ok" for value in service_health.values()):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=service_health)
        return {"status": "ok", **service_health}

    return app


app = create_app()
