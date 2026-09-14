from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

JobName = Annotated[str, Field(min_length=1, max_length=255, pattern=r"^\S(?:.*\S)?$")]


class VerificationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow: str = Field(pattern=r"^[A-Za-z0-9_-]+\.ya?ml$", description="Workflow filename, not display name.")
    required_jobs: list[JobName] = Field(min_length=1, max_length=30, description="Exact GitHub Actions job names.")
    event: Literal["pull_request"] = "pull_request"

    @field_validator("required_jobs")
    @classmethod
    def unique_jobs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Required job names must be unique")
        return value


class PipelineObservationConfig(BaseModel):
    """One repository connection and an explicit, bounded set of PRs to observe."""

    model_config = ConfigDict(extra="forbid")

    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*$")
    github_connector_id: UUID
    pull_numbers: list[Annotated[int, Field(gt=0)]] = Field(min_length=1, max_length=10)
    verification: VerificationConfig

    @field_validator("pull_numbers")
    @classmethod
    def unique_pulls(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("PR numbers must be unique")
        return value


class VerificationStatus(StrEnum):
    PASSED = "passed"
    WAITING = "waiting"
    FAILED = "failed"
    BLOCKED = "blocked"
    CLOSED = "closed"


class JobSnapshot(BaseModel):
    name: str
    status: str
    conclusion: str | None = None
    url: str | None = None


class RunSnapshot(BaseModel):
    id: int
    attempt: int
    head_sha: str
    status: str
    conclusion: str | None = None
    url: str
    jobs: list[JobSnapshot] = Field(default_factory=list)


class VerificationResult(BaseModel):
    status: VerificationStatus
    reason: str
    missing_jobs: list[str] = Field(default_factory=list)
    unsuccessful_jobs: list[str] = Field(default_factory=list)


class PullObservation(BaseModel):
    number: int
    head_sha: str
    base_sha: str
    url: str
    result: VerificationResult
    run: RunSnapshot | None = None


class PipelineObservation(BaseModel):
    kind: Literal["pipeline_observation"] = "pipeline_observation"
    observed_at: datetime
    config: PipelineObservationConfig
    pulls: list[PullObservation]
