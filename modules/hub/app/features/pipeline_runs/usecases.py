import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Annotated, Never
from uuid import UUID, uuid4

from app.features.pipeline_runs.models import (
    ExecutionAttempt,
    ExecutionAttemptKind,
    ExecutionAttemptState,
    PipelineRun,
    PipelineRunState,
)
from app.features.pipeline_runs.repos import PipelineRunRepository
from app.features.pipeline_runs.schemas import (
    ExecutionAttemptList,
    ExecutionAttemptRead,
    ImplementationRequest,
    LeaseGrant,
    LeaseMutation,
    LeaseRequest,
    PipelineRunAcquisition,
    PipelineRunList,
    PipelineRunRead,
    PreparedImplementationAttempt,
    PrepareImplementationAttempt,
)
from app.features.projects.linear import SelectActionableIssueUseCase
from app.features.projects.schemas import LinearIssue
from app.features.projects.services import ProjectError, ProjectService
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class PipelineRunUseCase:
    def __init__(
        self,
        repo: Annotated[PipelineRunRepository, Depends()],
        projects: Annotated[ProjectService, Depends()],
        selector: Annotated[SelectActionableIssueUseCase, Depends()],
    ):
        self.repo = repo
        self.projects = projects
        self.selector = selector

    async def list(self, project_id: UUID | None, offset: int, limit: int) -> PipelineRunList:
        async with AsyncTransaction() as session:
            rows, total = await self.repo.list(session, project_id=project_id, offset=offset, limit=limit)
            return PipelineRunList(items=[PipelineRunRead.model_validate(row) for row in rows], total_count=total)

    async def get(self, run_id: UUID) -> PipelineRunRead:
        async with AsyncTransaction() as session:
            run = await self.repo.get(session, run_id)
            if run is None:
                raise ProjectError(404, "Pipeline run not found")
            return PipelineRunRead.model_validate(run)

    async def list_attempts(self, run_id: UUID) -> ExecutionAttemptList:
        async with AsyncTransaction() as session:
            if await self.repo.get(session, run_id) is None:
                raise ProjectError(404, "Pipeline run not found")
            rows = await self.repo.list_attempts(session, run_id)
            return ExecutionAttemptList(
                items=[ExecutionAttemptRead.model_validate(row) for row in rows], total_count=len(rows)
            )

    async def acquire(self, project_id: UUID) -> PipelineRunAcquisition:
        async with AsyncTransaction() as session:
            project = await self.projects.get(session, project_id)
            if not project.enabled:
                raise ProjectError(422, "Project connection is disabled")
            expected_project_revision = project.revision
            existing = await self.repo.get_active(session, project_id)
            if existing is not None:
                return PipelineRunAcquisition(run=PipelineRunRead.model_validate(existing), created=False)
            handled_issue_ids = await self.repo.issue_ids(session, project_id)

        selection = await self.selector.execute(project_id, excluded_issue_ids=handled_issue_ids)
        issue = selection.selected
        if issue is None:
            return PipelineRunAcquisition(run=None, created=False, selection=selection)

        try:
            async with AsyncTransaction() as session:
                project = await self.projects.get(session, project_id, lock=True)
                if not project.enabled:
                    raise ProjectError(422, "Project connection is disabled")
                if project.revision != expected_project_revision:
                    raise ProjectError(409, "Project changed during pipeline run acquisition; retry")
                existing = await self.repo.get_active(session, project_id, lock=True)
                if existing is not None:
                    return PipelineRunAcquisition(run=PipelineRunRead.model_validate(existing), created=False)
                if issue.id in await self.repo.issue_ids(session, project_id):
                    raise ProjectError(409, "Selected Linear issue already has a pipeline run; retry selection")
                run = await self.repo.create(
                    session,
                    PipelineRun(
                        project_id=project_id,
                        project_revision=project.revision,
                        linear_issue_id=issue.id,
                        linear_issue_identifier=issue.identifier,
                        linear_issue_snapshot=issue.model_dump(mode="json"),
                        state=PipelineRunState.QUEUED,
                        branch=f"codex/{issue.identifier.lower()}",
                        revision=1,
                    ),
                )
                return PipelineRunAcquisition(
                    run=PipelineRunRead.model_validate(run), created=True, selection=selection
                )
        except IntegrityError:
            async with AsyncTransaction() as session:
                existing = await self.repo.get_active(session, project_id)
                if existing is not None:
                    return PipelineRunAcquisition(run=PipelineRunRead.model_validate(existing), created=False)
            raise ProjectError(409, "Pipeline run acquisition conflicted; retry") from None

    async def acquire_lease(self, run_id: UUID, request: LeaseRequest) -> LeaseGrant:
        now = datetime.now(UTC)
        token = uuid4()
        async with AsyncTransaction() as session:
            run = await self.repo.acquire_lease(
                session,
                run_id,
                owner=request.owner,
                token=token,
                now=now,
                expires_at=now + timedelta(seconds=request.ttl_seconds),
            )
            if run is None:
                await self._raise_lease_conflict(session, run_id, "acquire")
            return self._lease_grant(run)

    async def renew_lease(self, run_id: UUID, request: LeaseMutation) -> LeaseGrant:
        now = datetime.now(UTC)
        async with AsyncTransaction() as session:
            run = await self.repo.renew_lease(
                session,
                run_id,
                owner=request.owner,
                token=request.token,
                now=now,
                expires_at=now + timedelta(seconds=request.ttl_seconds),
            )
            if run is None:
                await self._raise_lease_conflict(session, run_id, "renew")
            return self._lease_grant(run)

    async def release_lease(self, run_id: UUID, request: LeaseMutation) -> None:
        now = datetime.now(UTC)
        async with AsyncTransaction() as session:
            run = await self.repo.release_lease(
                session,
                run_id,
                owner=request.owner,
                token=request.token,
                now=now,
            )
            if run is None:
                await self._raise_lease_conflict(session, run_id, "release")

    async def _raise_lease_conflict(self, session: AsyncSession, run_id: UUID, action: str) -> Never:
        run = await self.repo.get(session, run_id)
        if run is None:
            raise ProjectError(404, "Pipeline run not found")
        raise ProjectError(409, f"Pipeline run lease {action} was rejected")

    @staticmethod
    def _lease_grant(run: PipelineRun) -> LeaseGrant:
        if run.lease_owner is None or run.lease_token is None or run.lease_expires_at is None:
            raise RuntimeError("Lease update returned incomplete lease state")
        return LeaseGrant(
            run_id=run.id,
            owner=run.lease_owner,
            token=run.lease_token,
            expires_at=run.lease_expires_at,
            run_revision=run.revision,
        )

    async def prepare_implementation(
        self, run_id: UUID, request: PrepareImplementationAttempt
    ) -> PreparedImplementationAttempt:
        now = datetime.now(UTC)
        async with AsyncTransaction() as session:
            run = await self.repo.get_leased(
                session,
                run_id,
                owner=request.owner,
                token=request.token,
                now=now,
            )
            if run is None:
                await self._raise_lease_conflict(session, run_id, "prepare attempt")
            project = await self.projects.get(session, run.project_id)
            if not project.enabled or project.revision != run.project_revision:
                raise ProjectError(409, "Project changed after this pipeline run was acquired")
            existing = await self.repo.active_attempt(session, run_id)
            if existing is not None:
                implementation_request, request_digest, _ = self._build_implementation_request(
                    run,
                    project.repository,
                    request.base_branch,
                    idempotency_key=existing.idempotency_key,
                )
                if existing.request_digest != request_digest:
                    raise ProjectError(409, "The active attempt was prepared with a different request")
                return PreparedImplementationAttempt(
                    attempt=ExecutionAttemptRead.model_validate(existing),
                    request=ImplementationRequest.model_validate(existing.request_snapshot),
                    run_revision=run.revision,
                    created=False,
                )
            if run.revision != request.expected_run_revision:
                raise ProjectError(409, "Pipeline run changed; reload before preparing an attempt")
            if run.state != PipelineRunState.QUEUED:
                raise ProjectError(409, "Pipeline run is not ready for an implementation attempt")
            implementation_request, request_digest, idempotency_key = self._build_implementation_request(
                run, project.repository, request.base_branch
            )
            attempt = await self.repo.create_attempt(
                session,
                ExecutionAttempt(
                    pipeline_run_id=run.id,
                    attempt_number=await self.repo.next_attempt_number(session, run.id),
                    kind=ExecutionAttemptKind.IMPLEMENTATION,
                    state=ExecutionAttemptState.PLANNED,
                    request_snapshot=implementation_request.model_dump(mode="json"),
                    request_digest=request_digest,
                    idempotency_key=idempotency_key,
                ),
            )
            run.state = PipelineRunState.DISPATCHING
            run.revision += 1
            await session.flush()
            return PreparedImplementationAttempt(
                attempt=ExecutionAttemptRead.model_validate(attempt),
                request=implementation_request,
                run_revision=run.revision,
                created=True,
            )

    @staticmethod
    def _build_implementation_request(
        run: PipelineRun,
        repository: str,
        base_branch: str,
        *,
        idempotency_key: UUID | None = None,
    ) -> tuple[ImplementationRequest, str, UUID]:
        idempotency_key = idempotency_key or uuid4()
        marker = f"hub-attempt:{idempotency_key}"
        issue = LinearIssue.model_validate(run.linear_issue_snapshot)
        instructions = (
            f"Implement {issue.identifier} in {repository}. "
            f"Start from {base_branch}, use branch {run.branch}, follow the repository instructions, "
            "run the required checks, push the branch, and report the resulting commit and pull request."
        )
        snapshot = ImplementationRequest(
            correlation_marker=marker,
            repository=repository,
            base_branch=base_branch,
            head_branch=run.branch,
            issue=issue,
            instructions=instructions,
        )
        canonical = json.dumps(snapshot.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return snapshot, sha256(canonical.encode()).hexdigest(), idempotency_key
