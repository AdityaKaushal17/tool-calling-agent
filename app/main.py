from fastapi import FastAPI

from app.api.routes_agent import router as agent_router
from app.api.routes_auth import router as auth_router
from app.core.config import get_settings
from app.db.session import init_db
from app.logging_config import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(title=settings.app_name, version="0.1.0")

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(agent_router, prefix="/agent", tags=["agent"])

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
