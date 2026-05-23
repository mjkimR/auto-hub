from app.features.system_configs.models import SystemConfig
from app_base.base.deps.filters.combine import create_combined_filter_dependency
from app_base.base.deps.filters.decorators import filter_for
from app_base.base.deps.ordering.base import order_by_for
from app_base.base.deps.ordering.combine import create_order_by_dependency
from app_base.base.deps.query_options import create_list_query_options_dependency


@filter_for(bound_type=str, alias="name")
def filter_name(value: str | None):
    """Filter by name (case-insensitive substring)"""
    if value:
        return SystemConfig.name.ilike(f"%{value}%")
    return None


@order_by_for(alias="name")
def order_name(desc: bool):
    """Sort by name"""
    return SystemConfig.name.desc() if desc else SystemConfig.name.asc()


@order_by_for(alias="created_at")
def order_created_at(desc: bool):
    """Sort by creation time"""
    return SystemConfig.created_at.desc() if desc else SystemConfig.created_at.asc()


@order_by_for(alias="updated_at")
def order_updated_at(desc: bool):
    """Sort by update time"""
    return SystemConfig.updated_at.desc() if desc else SystemConfig.updated_at.asc()


@order_by_for(alias="id")
def order_id(desc: bool):
    """Sort by ID"""
    return SystemConfig.id.desc() if desc else SystemConfig.id.asc()


# Combine filters and ordering criteria into their respective dependencies
system_config_filters = create_combined_filter_dependency(
    filter_name,
)

system_config_ordering = create_order_by_dependency(
    order_name,
    order_created_at,
    order_updated_at,
    order_id,
    default_order="-created_at",
    tie_breaker=order_id,
)

# Export the combined list query options dependency
system_config_query_options = create_list_query_options_dependency(
    filters_dependency=system_config_filters,
    order_by_dependency=system_config_ordering,
)
