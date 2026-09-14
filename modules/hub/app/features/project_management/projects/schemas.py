from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.features.project_management.pipelines.schemas import (
    PipelineObservation,
    PipelineObservationConfig,
    VerificationConfig,
)
from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TemplateId = Literal["python-uv", "node-npm"]
MergeMethod = Literal["squash", "merge", "rebase"]


class GitHubAutomationConfig(BaseModel):
    """Per-project automation policy. Defaults preserve the original unattended flow."""

    model_config = ConfigDict(extra="forbid")

    auto_merge: bool = True
    merge_method: MergeMethod = "squash"
    auto_fix_ci: bool = True
    auto_fix_conflicts: bool = True
    auto_enroll_on_trigger: bool = True
    dispatch_interval_seconds: int = Field(default=60, ge=30, le=3600)


class GitHubProjectConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*$", max_length=255)
    github_connector_id: UUID
    verification: VerificationConfig
    template_id: TemplateId | None = None
    automation: GitHubAutomationConfig = Field(default_factory=GitHubAutomationConfig)

    @field_validator("repository", mode="before")
    @classmethod
    def normalize_repository(cls, value: str) -> str:
        return value.strip().lower() if isinstance(value, str) else value


class ProjectWrite(BaseModel):
    """A Hub project can exist before any external system is connected."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    github: GitHubProjectConnection | None = None
    enabled: bool = True

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_connection_payload(cls, value: object) -> object:
        """Translate the former flat connection shape during the API transition."""
        if not isinstance(value, dict) or "github" in value:
            return value
        result = dict(value)
        if "repository" in result:
            repository = result.pop("repository")
            connector_id = result.pop("github_connector_id", None)
            verification = result.pop("verification", None)
            template_id = result.pop("template_id", None)
            if connector_id is not None and verification is not None:
                github = {
                    "repository": repository,
                    "github_connector_id": connector_id,
                    "verification": verification,
                    "template_id": template_id,
                }
                automation = result.pop("automation", None)
                if automation is not None:
                    github["automation"] = automation
                result["github"] = github
        result.pop("linear_project_id", None)
        result.pop("linear_connector_id", None)
        result.pop("linear", None)
        return result

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Project name cannot be blank")
        return value.strip()

    def observation_config(self, pull_numbers: list[int]) -> PipelineObservationConfig:
        if self.github is None:
            raise ValueError("A GitHub connection is required for pipeline observation")
        return PipelineObservationConfig(
            repository=self.github.repository,
            github_connector_id=self.github.github_connector_id,
            verification=self.github.verification,
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
    github_login: str | None = Field(
        default=None, description="GitHub account the connector token acts as; Codex mentions are posted by it."
    )


class ProjectRead(UUIDSchemaMixin, TimestampSchemaMixin, ProjectWrite):
    model_config = ConfigDict(from_attributes=True)

    revision: int
    template_version: str | None
    last_check: ConnectionCheck | None
    # Compatibility fields for clients that have not yet adopted the nested connection shape.
    repository: str | None = None
    github_connector_id: UUID | None = None
    verification: VerificationConfig | None = None

    @model_validator(mode="before")
    @classmethod
    def nest_provider_connections(cls, value: object) -> object:
        if isinstance(value, dict) or not hasattr(value, "github_repository"):
            return value
        row: Any = value
        github = None
        if row.github_repository is not None:
            github = {
                "repository": row.github_repository,
                "github_connector_id": row.github_connector_id,
                "verification": row.verification,
                "template_id": row.template_id,
                "automation": row.automation,
            }
        return {
            "id": row.id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "name": row.name,
            "enabled": row.enabled,
            "github": github,
            "revision": row.revision,
            "template_version": row.template_version,
            "last_check": row.last_check,
            "repository": row.github_repository,
            "github_connector_id": row.github_connector_id,
            "verification": row.verification,
        }


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


class ProjectDispatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID


class TemplateRead(BaseModel):
    id: TemplateId
    name: str
    version: str
    changelog: str
    required_jobs: list[str]
    filename: str
    content: str
