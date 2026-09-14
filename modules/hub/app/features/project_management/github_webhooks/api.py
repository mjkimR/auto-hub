from typing import Annotated

from app.common.config import get_github_webhook_config
from app.features.project_management.github_webhooks.repos import GitHubWebhookRepository
from app.features.project_management.github_webhooks.usecases import GitHubWebhookUseCase
from app.features.project_management.pipeline_runs.repos import PipelineRunRepository
from app.features.project_management.pipeline_runs.usecases.lifecycle import PipelineRunUseCase
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status

router = APIRouter(prefix="/github/webhooks", tags=["GitHub Webhook"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def receive_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    lifecycle: Annotated[PipelineRunUseCase, Depends()],
    x_github_delivery: Annotated[str | None, Header()] = None,
    x_github_event: Annotated[str | None, Header()] = None,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
):
    config = get_github_webhook_config()
    secret = config.GITHUB_WEBHOOK_SECRET
    if secret is None:
        raise HTTPException(status_code=503, detail="GitHub webhooks are not configured")
    if not x_github_delivery or not x_github_event:
        raise HTTPException(status_code=400, detail="Missing GitHub delivery headers")
    raw_body = await request.body()
    use_case = GitHubWebhookUseCase(GitHubWebhookRepository(), PipelineRunRepository(), lifecycle)
    if not use_case.verify_signature(secret.get_secret_value(), raw_body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid GitHub webhook signature")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid GitHub webhook payload") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid GitHub webhook payload")
    if not await use_case.receive(x_github_delivery, x_github_event, raw_body, payload):
        return {"status": "duplicate"}
    background_tasks.add_task(use_case.process, x_github_delivery, payload, x_github_event)
    return {"status": "accepted"}
