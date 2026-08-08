from celery import shared_task

from app.agent.graph import run_agent_request


@shared_task(bind=True, name="run_agent_task")
def run_agent_task(self, task_id: str, user_id: int, user_email: str, message: str) -> dict:
    return run_agent_request(task_id=task_id, user_id=user_id, user_email=user_email, request_text=message)
