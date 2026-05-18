import asyncio
import uuid
from unittest.mock import MagicMock, patch

from app.features.dispatchers.services import DispatcherService


async def test_dispatch_jobs_timeout(monkeypatch):
    from app.common.config import SchedulerDefaults
    from app.features.schedule_configs.schemas import ScheduleConfigRead
    from app.features.schedule_jobs.schemas import ScheduleJobRead

    mock_job = MagicMock(spec=ScheduleJobRead)
    mock_config = MagicMock(spec=ScheduleConfigRead)
    run_id = uuid.uuid4()

    # Use a real SchedulerDefaults object but mock the property it uses for timeout
    settings = SchedulerDefaults()

    service = DispatcherService(
        job_repo=MagicMock(),
        settings=settings,
    )

    # Override global_timeout directly on the service object
    service.global_timeout = 0.01

    async def slow_dispatch(*args, **kwargs):
        await asyncio.sleep(0.1)

    service._dispatch = slow_dispatch

    with patch("app.features.dispatchers.services.logger") as mock_logger:
        await service.dispatch_jobs([(mock_job, mock_config)], run_id)
        mock_logger.error.assert_called_once()
        assert "timed out after" in mock_logger.error.call_args[0][0]
