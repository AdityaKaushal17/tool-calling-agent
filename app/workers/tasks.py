from app.agent.graph import run_agent_request
from app.workers.celery_app import celery_app


# Bound to our app explicitly (not @shared_task): FastAPI runs sync endpoints in a
# threadpool, where a shared_task resolves to Celery's *default* app and silently
# falls back to AMQP unless a CELERY_BROKER_URL env var happens to be set.
@celery_app.task(bind=True, name="run_agent_task")
def run_agent_task(self, task_id: str, user_id: int, user_email: str, message: str) -> dict:
    return run_agent_request(task_id=task_id, user_id=user_id, user_email=user_email, request_text=message)
