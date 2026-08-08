from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import RedisRateLimiter
from app.core.security import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.workers.celery_app import celery_app
from app.workers.tasks import run_agent_task


router = APIRouter()


class AgentRunRequest(BaseModel):
    message: str = Field(min_length=1)


def _rate_limiter() -> RedisRateLimiter:
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return RedisRateLimiter(redis_client)


@router.post("/run")
def run_agent(payload: AgentRunRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    settings = get_settings()
    limiter = _rate_limiter()
    limit_result = limiter.allow(f"rate-limit:user:{current_user.id}", settings.rate_limit_per_hour, 60 * 60)
    if not limit_result.allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    task_uuid = str(uuid4())
    async_result = run_agent_task.apply_async(args=[task_uuid, current_user.id, current_user.email, payload.message], task_id=task_uuid)
    return {"task_id": async_result.id, "status": async_result.status}


@router.get("/status/{task_id}")
def agent_status(task_id: str) -> dict[str, object]:
    task_result = AsyncResult(task_id, app=celery_app)
    response: dict[str, object] = {"task_id": task_id, "state": task_result.state}
    if task_result.successful():
        response["result"] = task_result.result
    elif task_result.failed():
        response["error"] = str(task_result.result)
    return response
