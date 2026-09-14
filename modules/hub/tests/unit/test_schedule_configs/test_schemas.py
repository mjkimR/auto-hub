import pytest
from app.features.scheduling.schedule_configs.schemas import ScheduleConfigCreate, ScheduleConfigPatch


def test_schedule_config_create_invalid_cron():
    with pytest.raises(ValueError) as exc:
        ScheduleConfigCreate(
            name="Invalid Cron",
            task_func="tasks.dummy",
            cron_expression="invalid cron expression",
        )
    assert "Invalid cron_expression" in str(exc.value)


def test_schedule_config_create_mutually_exclusive_triggers():
    with pytest.raises(ValueError) as exc:
        ScheduleConfigCreate(
            name="Both Triggers",
            task_func="tasks.dummy",
            cron_expression="0 0 * * *",
            interval_seconds=60,
        )
    assert "cron_expression and interval_seconds are mutually exclusive." in str(exc.value)


def test_schedule_config_create_missing_triggers():
    with pytest.raises(ValueError) as exc:
        ScheduleConfigCreate(
            name="No Triggers",
            task_func="tasks.dummy",
        )
    assert "Either cron_expression or interval_seconds must be provided." in str(exc.value)


def test_schedule_config_patch_invalid_cron():
    with pytest.raises(ValueError) as exc:
        ScheduleConfigPatch(
            cron_expression="invalid cron expression",
        )
    assert "Invalid cron_expression" in str(exc.value)


def test_schedule_config_patch_mutually_exclusive_triggers():
    with pytest.raises(ValueError) as exc:
        ScheduleConfigPatch(
            cron_expression="0 0 * * *",
            interval_seconds=60,
        )
    assert "cron_expression and interval_seconds are mutually exclusive." in str(exc.value)


def test_cron_expression_caching():
    from app.features.scheduling.schedule_configs.schemas import _check_cron_expression, _validate_cron_expression

    # Clear cache first to have clean stats
    _check_cron_expression.cache_clear()

    # 1. Test success caching
    _validate_cron_expression("*/5 * * * *")
    info = _check_cron_expression.cache_info()
    assert info.misses == 1
    assert info.hits == 0

    # Recheck the same valid expression should hit the cache
    _validate_cron_expression("*/5 * * * *")
    info = _check_cron_expression.cache_info()
    assert info.misses == 1
    assert info.hits == 1

    # 2. Test failure caching
    with pytest.raises(ValueError):
        _validate_cron_expression("invalid_cron_here")
    info = _check_cron_expression.cache_info()
    assert info.misses == 2
    assert info.hits == 1

    # Recheck the same invalid expression should hit the cache
    with pytest.raises(ValueError):
        _validate_cron_expression("invalid_cron_here")
    info = _check_cron_expression.cache_info()
    assert info.misses == 2
    assert info.hits == 2
