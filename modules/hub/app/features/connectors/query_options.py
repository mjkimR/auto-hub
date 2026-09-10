from app.features.connectors.models import Connector
from app_layer_base.base.deps.filters.combine import create_combined_filter_dependency
from app_layer_base.base.deps.filters.decorators import filter_for
from app_layer_base.base.deps.ordering.base import order_by_for
from app_layer_base.base.deps.ordering.combine import create_order_by_dependency
from app_layer_base.base.deps.query_options import create_list_query_options_dependency


@filter_for(bound_type=str, alias="name")
def filter_name(value: str | None):
    return Connector.name.ilike(f"%{value}%") if value else None


@filter_for(bound_type=str, alias="provider")
def filter_provider(value: str | None):
    return Connector.provider == value if value else None


@filter_for(bound_type=bool, alias="enabled")
def filter_enabled(value: bool | None):
    return Connector.enabled.is_(value) if value is not None else None


@order_by_for(alias="name")
def order_name(desc: bool):
    return Connector.name.desc() if desc else Connector.name.asc()


@order_by_for(alias="created_at")
def order_created_at(desc: bool):
    return Connector.created_at.desc() if desc else Connector.created_at.asc()


@order_by_for(alias="updated_at")
def order_updated_at(desc: bool):
    return Connector.updated_at.desc() if desc else Connector.updated_at.asc()


@order_by_for(alias="id")
def order_id(desc: bool):
    return Connector.id.desc() if desc else Connector.id.asc()


connector_filters = create_combined_filter_dependency(filter_name, filter_provider, filter_enabled)
connector_ordering = create_order_by_dependency(
    order_name,
    order_created_at,
    order_updated_at,
    order_id,
    default_order="-created_at",
    tie_breaker=order_id,
)
connector_query_options = create_list_query_options_dependency(
    filters_dependency=connector_filters,
    order_by_dependency=connector_ordering,
)
