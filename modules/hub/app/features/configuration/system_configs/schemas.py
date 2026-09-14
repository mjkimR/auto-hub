from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field


class SystemConfigBase(BaseModel):
    name: str = Field(description="The name of the system_config.")
    data: dict | None = Field(default_factory=dict, description="The data of the system_config.")


class SystemConfigCreate(SystemConfigBase):
    pass


class SystemConfigPut(SystemConfigBase):
    pass


class SystemConfigPatch(BaseModel):
    name: str | None = Field(default=None, description="The name of the system_config.")
    data: dict | None = Field(default=None, description="The data of the system_config.")


class SystemConfigRead(UUIDSchemaMixin, TimestampSchemaMixin, SystemConfigBase):
    model_config = ConfigDict(from_attributes=True)
