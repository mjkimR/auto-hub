from app.features.project_management.github_webhooks.models import GitHubWebhookDelivery
from app.features.project_management.projects.models import Project
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class GitHubWebhookRepository:
    async def create(self, session: AsyncSession, delivery: GitHubWebhookDelivery) -> GitHubWebhookDelivery:
        session.add(delivery)
        await session.flush()
        return delivery

    async def project_for_repository(self, session: AsyncSession, repository: str) -> Project | None:
        return await session.scalar(select(Project).where(Project.github_repository == repository.lower()))

    async def get(self, session: AsyncSession, delivery_id: str) -> GitHubWebhookDelivery | None:
        return await session.scalar(
            select(GitHubWebhookDelivery).where(GitHubWebhookDelivery.delivery_id == delivery_id)
        )
