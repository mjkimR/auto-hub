from uuid import UUID

from app.features.schedule_jobs.models import ScheduleJob, ScheduleJobStatus
from app_layer_base.base.deps.filters.combine import create_combined_filter_dependency
from app_layer_base.base.deps.filters.decorators import filter_for
from app_layer_base.base.deps.ordering.base import order_by_for
from app_layer_base.base.deps.ordering.combine import create_order_by_dependency
from app_layer_base.base.deps.query_options import create_list_query_options_dependency


@filter_for(bound_type=str, alias="name")
def filter_name(value: str | None):
    """Filter by name (case-insensitive substring)"""
    if value:
        return ScheduleJob.name.ilike(f"%{value}%")
    return None


@filter_for(bound_type=ScheduleJobStatus, alias="status")
def filter_status(value: ScheduleJobStatus | None):
    """Filter by execution status"""
    if value:
        return ScheduleJob.status == value.value
    return None


@filter_for(bound_type=UUID, alias="schedule_config_id")
def filter_schedule_config_id(value: UUID | None):
    """Filter by schedule configuration ID"""
    if value:
        return ScheduleJob.schedule_config_id == value
    return None


@filter_for(bound_type=UUID, alias="dispatcher_run_id")
def filter_dispatcher_run_id(value: UUID | None):
    """Filter by dispatcher run ID"""
    if value:
        return ScheduleJob.dispatcher_run_id == value
    return None


@filter_for(bound_type=bool, alias="retry_need")
def filter_retry_need(value: bool | None):
    """Filter by whether retry is needed"""
    if value is not None:
        return ScheduleJob.retry_need.is_(value)
    return None


@order_by_for(alias="name")
def order_name(desc: bool):
    """Sort by name"""
    return ScheduleJob.name.desc() if desc else ScheduleJob.name.asc()


@order_by_for(alias="status")
def order_status(desc: bool):
    """Sort by status"""
    return ScheduleJob.status.desc() if desc else ScheduleJob.status.asc()


@order_by_for(alias="started_at")
def order_started_at(desc: bool):
    """Sort by execution start time"""
    return ScheduleJob.started_at.desc() if desc else ScheduleJob.started_at.asc()


@order_by_for(alias="finished_at")
def order_finished_at(desc: bool):
    """Sort by execution finish time"""
    return ScheduleJob.finished_at.desc() if desc else ScheduleJob.finished_at.asc()


@order_by_for(alias="created_at")
def order_created_at(desc: bool):
    """Sort by creation time"""
    return ScheduleJob.created_at.desc() if desc else ScheduleJob.created_at.asc()


@order_by_for(alias="updated_at")
def order_updated_at(desc: bool):
    """Sort by update time"""
    return ScheduleJob.updated_at.desc() if desc else ScheduleJob.updated_at.asc()


@order_by_for(alias="id")
def order_id(desc: bool):
    """Sort by ID"""
    return ScheduleJob.id.desc() if desc else ScheduleJob.id.asc()


# Combine filters and ordering criteria into their respective dependencies
schedule_job_filters = create_combined_filter_dependency(
    filter_name,
    filter_status,
    filter_schedule_config_id,
    filter_dispatcher_run_id,
    filter_retry_need,
)

schedule_job_ordering = create_order_by_dependency(
    order_name,
    order_status,
    order_started_at,
    order_finished_at,
    order_created_at,
    order_updated_at,
    order_id,
    default_order="-started_at",
    tie_breaker=order_id,
)

# Export the combined list query options dependency
schedule_job_query_options = create_list_query_options_dependency(
    filters_dependency=schedule_job_filters,
    order_by_dependency=schedule_job_ordering,
)
