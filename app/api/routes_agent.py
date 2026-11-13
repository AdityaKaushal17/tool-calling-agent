from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.rate_limit import RedisRateLimiter
from app.core.security import get_current_user
from app.db.models import User
from app.workers.celery_app import celery_app
from app.workers.tasks import run_agent_task


router = APIRouter()


class AgentRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


TASK_OWNER_TTL_SECONDS = 60 * 60 * 24


def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def _owner_key(task_id: str) -> str:
    return f"task-owner:{task_id}"


@router.post("/run")
def run_agent(payload: AgentRunRequest, current_user: User = Depends(get_current_user)) -> dict[str, str]:
    settings = get_settings()
    redis_client = _redis()
    try:
        limit_result = RedisRateLimiter(redis_client).allow(f"rate-limit:user:{current_user.id}", settings.rate_limit_per_hour, 60 * 60)
    except RedisError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue unavailable, try again shortly") from exc
    if not limit_result.allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    task_uuid = str(uuid4())
    redis_client.set(_owner_key(task_uuid), current_user.id, ex=TASK_OWNER_TTL_SECONDS)
    async_result = run_agent_task.apply_async(args=[task_uuid, current_user.id, current_user.email, payload.message], task_id=task_uuid)
    return {"task_id": async_result.id, "status": async_result.status}


@router.get("/status/{task_id}")
def agent_status(task_id: str, current_user: User = Depends(get_current_user)) -> dict[str, object]:
    try:
        owner = _redis().get(_owner_key(task_id))
    except RedisError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue unavailable, try again shortly") from exc
    # Same 404 for "doesn't exist" and "not yours" so task ids can't be probed.
    if owner is None or int(owner) != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task_result = AsyncResult(task_id, app=celery_app)
    response: dict[str, object] = {"task_id": task_id, "state": task_result.state}
    if task_result.successful():
        response["result"] = task_result.result
    elif task_result.failed():
        response["error"] = str(task_result.result)
    return response
