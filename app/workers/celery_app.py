from celery import Celery

from app.core.config import get_settings


settings = get_settings()

celery_app = Celery(
    "tool_agent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    result_expires=60 * 60 * 24,
    broker_connection_retry_on_startup=True,
    # Managed Redis (Render Key Value / Upstash) closes idle connections; keep them healthy.
    broker_transport_options={"health_check_interval": 30},
    redis_backend_health_check_interval=30,
)
