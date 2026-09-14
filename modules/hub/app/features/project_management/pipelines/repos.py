from uuid import UUID

from app.features.configuration.connectors.models import Connector
from app.features.execution.task_states import store
from app.features.scheduling.schedule_configs.models import ScheduleConfig
from sqlalchemy.ext.asyncio import AsyncSession


class PipelineObservationRepository:
    async def get_connector(self, session: AsyncSession, connector_id: UUID) -> Connector | None:
        return await session.get(Connector, connector_id)

    async def get_schedule(self, session: AsyncSession, schedule_id: UUID) -> ScheduleConfig | None:
        return await session.get(ScheduleConfig, schedule_id)

    async def load(self, session: AsyncSession, schedule_id: UUID) -> dict | None:
        return await store.load(session, schedule_id)

    async def save(self, session: AsyncSession, schedule_id: UUID, data: dict) -> None:
        await store.upsert(session, schedule_id, data)
