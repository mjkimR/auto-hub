from app.features.scheduling.schedule_configs.models import ScheduleConfig
from app_layer_base.base.deps.filters.combine import create_combined_filter_dependency
from app_layer_base.base.deps.filters.decorators import filter_for
from app_layer_base.base.deps.ordering.base import order_by_for
from app_layer_base.base.deps.ordering.combine import create_order_by_dependency
from app_layer_base.base.deps.query_options import create_list_query_options_dependency


@filter_for(bound_type=str, alias="name")
def filter_name(value: str | None):
    """Filter by name (case-insensitive substring)"""
    if value:
        return ScheduleConfig.name.ilike(f"%{value}%")
    return None


@filter_for(bound_type=str, alias="task_func")
def filter_task_func(value: str | None):
    """Filter by task function path (case-insensitive substring)"""
    if value:
        return ScheduleConfig.task_func.ilike(f"%{value}%")
    return None


@filter_for(bound_type=bool, alias="enabled")
def filter_enabled(value: bool | None):
    """Filter by enabled status"""
    if value is not None:
        return ScheduleConfig.enabled.is_(value)
    return None


@order_by_for(alias="name")
def order_name(desc: bool):
    """Sort by name"""
    return ScheduleConfig.name.desc() if desc else ScheduleConfig.name.asc()


@order_by_for(alias="created_at")
def order_created_at(desc: bool):
    """Sort by creation time"""
    return ScheduleConfig.created_at.desc() if desc else ScheduleConfig.created_at.asc()


@order_by_for(alias="updated_at")
def order_updated_at(desc: bool):
    """Sort by update time"""
    return ScheduleConfig.updated_at.desc() if desc else ScheduleConfig.updated_at.asc()


@order_by_for(alias="next_run_at")
def order_next_run_at(desc: bool):
    """Sort by next run time"""
    return ScheduleConfig.next_run_at.desc() if desc else ScheduleConfig.next_run_at.asc()


@order_by_for(alias="last_run_at")
def order_last_run_at(desc: bool):
    """Sort by last run time"""
    return ScheduleConfig.last_run_at.desc() if desc else ScheduleConfig.last_run_at.asc()


@order_by_for(alias="id")
def order_id(desc: bool):
    """Sort by ID"""
    return ScheduleConfig.id.desc() if desc else ScheduleConfig.id.asc()


# Combine filters and ordering criteria into their respective dependencies
schedule_config_filters = create_combined_filter_dependency(
    filter_name,
    filter_task_func,
    filter_enabled,
)

schedule_config_ordering = create_order_by_dependency(
    order_name,
    order_created_at,
    order_updated_at,
    order_next_run_at,
    order_last_run_at,
    order_id,
    default_order="-created_at",
    tie_breaker=order_id,
)

# Export the combined list query options dependency
schedule_config_query_options = create_list_query_options_dependency(
    filters_dependency=schedule_config_filters,
    order_by_dependency=schedule_config_ordering,
)
