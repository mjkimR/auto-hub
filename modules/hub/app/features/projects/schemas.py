from datetime import datetime
from typing import Literal
from uuid import UUID

from app.features.pipelines.schemas import PipelineObservation, PipelineObservationConfig, VerificationConfig
from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field, field_validator

TemplateId = Literal["python-uv", "node-npm"]


class ProjectWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*$", max_length=255)
    linear_project_id: UUID
    github_connector_id: UUID
    linear_connector_id: UUID | None = None
    verification: VerificationConfig
    enabled: bool = True
    template_id: TemplateId | None = None

    @field_validator("repository", mode="before")
    @classmethod
    def normalize_repository(cls, value: str) -> str:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Project name cannot be blank")
        return value.strip()

    def observation_config(self, pull_numbers: list[int]) -> PipelineObservationConfig:
        return PipelineObservationConfig(
            repository=self.repository,
            linear_project_id=self.linear_project_id,
            github_connector_id=self.github_connector_id,
            verification=self.verification,
            pull_numbers=pull_numbers,
        )


class ConnectionCheckItem(BaseModel):
    name: str
    status: Literal["passed", "failed", "skipped"]
    detail: str


class ConnectionCheck(BaseModel):
    checked_at: datetime
    project_revision: int
    ready: bool
    checks: list[ConnectionCheckItem]
    observation: PipelineObservation | None = None


class ProjectRead(UUIDSchemaMixin, TimestampSchemaMixin, ProjectWrite):
    model_config = ConfigDict(from_attributes=True)

    revision: int
    template_version: str | None
    last_check: ConnectionCheck | None


class ProjectUpdate(ProjectWrite):
    expected_revision: int = Field(ge=1, description="Reject edits based on an outdated project version.")


class ProjectList(BaseModel):
    items: list[ProjectRead]
    total_count: int


class CheckRequest(BaseModel):
    pull_number: int = Field(gt=0)


class ImportScheduleRequest(BaseModel):
    schedule_id: UUID


class ProjectObservationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    pull_numbers: list[int] = Field(min_length=1, max_length=10)

    @field_validator("pull_numbers")
    @classmethod
    def validate_pulls(cls, value: list[int]) -> list[int]:
        if any(number <= 0 for number in value) or len(set(value)) != len(value):
            raise ValueError("PR numbers must be positive and unique")
        return value


class TemplateRead(BaseModel):
    id: TemplateId
    name: str
    version: str
    changelog: str
    required_jobs: list[str]
    filename: str
    content: str
