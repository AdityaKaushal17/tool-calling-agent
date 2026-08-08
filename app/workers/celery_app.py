from celery import Celery

from app.core.config import get_settings


settings = get_settings()

celery_app = Celery(
    "tool_agent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_track_started=True,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
)

celery_app.autodiscover_tasks(["app.workers"])
