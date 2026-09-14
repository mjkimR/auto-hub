import uuid
from unittest.mock import MagicMock, patch

import pytest
from app.features.execution.tasks.core.context import TaskMeta
from app.features.execution.tasks.core.log import logger


@pytest.fixture
def mock_core_logger():
    with patch("app.features.execution.tasks.core.log.core_logger") as mock:
        mock_bound = MagicMock()
        mock.bind.return_value = mock_bound
        yield mock


@pytest.fixture
def mock_get_task_meta():
    with patch("app.features.execution.tasks.core.log.get_task_meta") as mock:
        yield mock


def test_logger_without_meta(mock_core_logger, mock_get_task_meta):
    mock_get_task_meta.return_value = None

    # It should return core_logger directly
    assert logger._bound_logger() == mock_core_logger


def test_logger_with_meta(mock_core_logger, mock_get_task_meta):
    config_id = uuid.uuid4()
    run_id = uuid.uuid4()
    mock_meta = TaskMeta(
        config_id=config_id,
        config_name="test_config",
        run_id=run_id,
    )
    mock_get_task_meta.return_value = mock_meta

    logger._bound_logger()

    mock_core_logger.bind.assert_called_once_with(
        config_id=str(config_id),
        config_name="test_config",
        run_id=str(run_id),
        custom_prefix=f"[test_config][run:{str(run_id).split('-')[0]}] ",
    )


@pytest.mark.parametrize("method_name", ["debug", "info", "warning", "error", "critical", "exception"])
def test_logger_methods(mock_core_logger, mock_get_task_meta, method_name):
    # Setup mock to return a mock for opt()
    mock_opt = MagicMock()
    if mock_get_task_meta.return_value is None:
        # _bound_logger returns core_logger directly
        mock_core_logger.opt.return_value = mock_opt
    else:
        mock_core_logger.bind.return_value.opt.return_value = mock_opt

    # Call the method
    method = getattr(logger, method_name)
    method("test message", "arg1", kwarg1="val1")

    # Assert opt() was called with depth=1
    if mock_get_task_meta.return_value is None:
        mock_core_logger.opt.assert_called_once_with(depth=1)
    else:
        mock_core_logger.bind.return_value.opt.assert_called_once_with(depth=1)

    # Assert the actual log method (debug, info, etc) was called on the opt mock
    mock_log_method = getattr(mock_opt, method_name)
    mock_log_method.assert_called_once_with("test message", "arg1", kwarg1="val1")
