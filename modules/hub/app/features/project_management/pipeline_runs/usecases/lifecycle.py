from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Annotated, Never
from uuid import UUID, uuid4

from app.features.ai_catalogs.models import (
    AICatalog,
    AICatalogKind,
    AICatalogState,
)
from app.features.ai_catalogs.repos import AICatalogRepository
from app.features.ai_catalogs.services import AICatalogService
from app.features.project_management.pipeline_runs.adapters.base import DeliveryTarget
from app.features.project_management.pipeline_runs.adapters.codex_github_mention import CodexGithubMentionAdapter
from app.features.project_management.pipeline_runs.adapters.registry import resolve_execution_adapter
from app.features.project_management.pipeline_runs.github import read_pull_request
from app.features.project_management.pipeline_runs.models import (
    ExecutionAttempt,
    ExecutionAttemptKind,
    ExecutionAttemptState,
    ExecutionDelivery,
    ExecutionReply,
    PipelineRun,
    PipelineRunState,
)
from app.features.project_management.pipeline_runs.repos import PipelineRunRepository
from app.features.project_management.pipeline_runs.schemas import (
    AttachPRRequest,
    CompleteAttemptRequest,
    EnrollPullRequest,
    ExecutionAttemptList,
    ExecutionAttemptRead,
    ExecutionDeliveryRead,
    ExecutionReplyRead,
    ImplementationRequest,
    LeaseGrant,
    LeaseMutation,
    LeaseRequest,
    PauseRunRequest,
    PipelineRunList,
    PipelineRunRead,
    PreparedImplementationAttempt,
    PrepareImplementationAttempt,
    PullRequestSnapshot,
)
from app.features.project_management.pipelines import services as pipeline_services
from app.features.project_management.pipelines.github import GitHubActionsReader, GitHubObservationError
from app.features.project_management.pipelines.schemas import VerificationStatus
from app.features.project_management.pipelines.services import PipelineConfigurationError, PipelineObservationService
from app.features.project_management.projects.schemas import ProjectRead
from app.features.project_management.projects.services import ProjectError, ProjectService
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

ACTIVE_RUN_CONFLICT = "This pull request already has an active pipeline run"
DISPATCH_IO_SECONDS = 30
DISPATCH_LEASE_SECONDS = 90
PROJECT_CHANGED_BLOCK_REASON = (
    "Project changed after this pipeline run was enrolled; resume to continue with the new settings, "
    "or cancel it and enroll the pull request again if its repository or GitHub connection changed"
)
IN_FLIGHT_RESUME_WARNING = (
    " The agent may still be working on the previous request; resuming now can start duplicate work on the same branch."
)
GITHUB_BINDING_CHANGED_CONFLICT = (
    "Project repository or GitHub connection changed after this pipeline run was enrolled; "
    "cancel it and enroll the pull request again"
)


def _utc(value: datetime) -> datetime:
    # SQLite returns naive values for DateTime(timezone=True); persisted times are UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class PipelineRunUseCase:
    def __init__(
        self,
        repo: Annotated[PipelineRunRepository, Depends()],
        projects: Annotated[ProjectService, Depends()],
        observer: Annotated[PipelineObservationService, Depends()],
        ai_catalogs: Annotated[AICatalogService | None, Depends(AICatalogService)] = None,
    ):
        self.repo = repo
        self.projects = projects
        self.observer = observer
        self.ai_catalogs = ai_catalogs

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

    async def list_deliveries(self, run_id: UUID, attempt_id: UUID) -> list[ExecutionDeliveryRead]:
        async with AsyncTransaction() as session:
            attempt = await self.repo.get_attempt(session, attempt_id)
            if attempt is None or attempt.pipeline_run_id != run_id:
                raise ProjectError(404, "Execution attempt not found for this pipeline run")
            return [
                ExecutionDeliveryRead.model_validate(row)
                for row in await self.repo.list_deliveries(session, attempt_id)
            ]

    async def list_replies(self, run_id: UUID, attempt_id: UUID) -> list[ExecutionReplyRead]:
        async with AsyncTransaction() as session:
            attempt = await self.repo.get_attempt(session, attempt_id)
            if attempt is None or attempt.pipeline_run_id != run_id:
                raise ProjectError(404, "Execution attempt not found for this pipeline run")
            return [ExecutionReplyRead.model_validate(row) for row in await self.repo.list_replies(session, attempt_id)]

    async def enroll(self, project_id: UUID, request: EnrollPullRequest) -> PipelineRunRead:
        async with AsyncTransaction() as session:
            project = await self.projects.get(session, project_id)
            if not project.enabled:
                raise ProjectError(422, "Project is disabled")
            if project.github_repository is None or project.github_connector_id is None:
                raise ProjectError(422, "Project missing GitHub connection for pipeline run")
            if await self.repo.get_active_for_pull(session, project_id, request.pull_number) is not None:
                raise ProjectError(409, ACTIVE_RUN_CONFLICT)
            repository, connector_id, expected_revision = (
                project.github_repository,
                project.github_connector_id,
                project.revision,
            )

        # Keep GitHub reads outside database transactions.
        try:
            token = await self.observer.get_token(connector_id, "github")
        except PipelineConfigurationError as exc:
            raise ProjectError(422, str(exc)) from None
        try:
            async with asyncio.timeout(30):
                async with pipeline_services.create_github_client(token) as client:
                    snapshot = await read_pull_request(GitHubActionsReader(client), repository, request.pull_number)
        except TimeoutError:
            raise ProjectError(504, "Pull request read exceeded its time budget") from None

        try:
            async with AsyncTransaction() as session:
                project = await self.projects.get(session, project_id, lock=True)
                if not project.enabled:
                    raise ProjectError(422, "Project is disabled")
                if project.revision != expected_revision:
                    raise ProjectError(409, "Project changed during pull request enrollment; retry")
                if await self.repo.get_active_for_pull(session, project_id, snapshot.number, lock=True) is not None:
                    raise ProjectError(409, ACTIVE_RUN_CONFLICT)
                catalog = await self._default_catalog(session)
                run = await self.repo.create(
                    session,
                    PipelineRun(
                        project_id=project_id,
                        ai_catalog_id=catalog.id,
                        project_revision=project.revision,
                        github_repository=project.github_repository,
                        github_connector_id=project.github_connector_id,
                        pull_number=snapshot.number,
                        pull_url=snapshot.url,
                        pull_snapshot=snapshot.model_dump(mode="json"),
                        state=PipelineRunState.QUEUED,
                        branch=snapshot.head_ref,
                        revision=1,
                    ),
                )
                return PipelineRunRead.model_validate(run)
        except IntegrityError:
            raise ProjectError(409, ACTIVE_RUN_CONFLICT) from None

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
                raise ProjectError(409, "Project changed after this pipeline run was enrolled")
            existing = await self.repo.active_attempt(session, run_id)
            if existing is not None:
                _, request_digest, _ = self._build_implementation_request(
                    run, self._github_repository(project), idempotency_key=existing.idempotency_key
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
                run, self._github_repository(project)
            )
            attempt = await self.repo.create_attempt(
                session,
                ExecutionAttempt(
                    pipeline_run_id=run.id,
                    attempt_number=await self.repo.next_attempt_number(session, run.id),
                    epoch=run.epoch,
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

    async def advance_run(
        self,
        run_id: UUID,
        *,
        owner: str,
        token: UUID,
        observer: PipelineObservationService,
    ) -> PipelineRunRead:
        now = datetime.now(UTC)
        async with AsyncTransaction() as session:
            run = await self.repo.get_leased(
                session,
                run_id,
                owner=owner,
                token=token,
                now=now,
            )
            if run is None:
                await self._raise_lease_conflict(session, run_id, "advance run")
            project = await self.projects.get(session, run.project_id)
            if (
                not project.enabled
                or project.revision != run.project_revision
                or project.github_repository is None
                or project.github_connector_id is None
            ):
                return await self._block_for_project_change(session, run, now)

            # A planned delivery must be reconciled or posted before a run can advance.
            if run.state == PipelineRunState.IMPLEMENTING:
                attempt = await self.repo.active_attempt(session, run.id)
                if attempt is None:
                    raise ProjectError(409, "Pipeline run has no active implementation attempt")
                delivery = await self.repo.latest_delivery(session, attempt.id)
                posted_at = (
                    _utc(delivery.posted_at) if delivery is not None and delivery.posted_at is not None else None
                )
                pr = await observer.get_pull_request(
                    project.github_connector_id, project.github_repository, run.pull_number
                )
                if pr.get("state") == "closed":
                    await self._finish_closed_pull(session, run, pr, now)
                    return PipelineRunRead.model_validate(run)
                delivery_head = PullRequestSnapshot.model_validate(attempt.request_snapshot["pull_request"]).head_sha
                if delivery is not None and delivery.posted_at is not None and pr["head"]["sha"] != delivery_head:
                    run.state = PipelineRunState.AWAITING_CI
                    run.next_action_at = None
                    run.revision += 1
                    attempt.state = ExecutionAttemptState.RUNNING
                    await session.flush()
                    return PipelineRunRead.model_validate(run)
                target = DeliveryTarget(project.github_connector_id, project.github_repository, run.pull_number)
                adapter = await resolve_execution_adapter(session, run.ai_catalog_id)
                replies = await adapter.collect_replies(observer, target, posted_at)
                for reply in replies:
                    if reply.external_id is not None and not await self.repo.has_reply_comment(
                        session, reply.external_id
                    ):
                        await self.repo.create_reply(
                            session,
                            ExecutionReply(
                                execution_attempt_id=attempt.id,
                                comment_id=reply.external_id,
                                author=reply.author,
                                replied_at=reply.replied_at,
                                excerpt=reply.body.strip()[:500] or None,
                                is_quota_limit=reply.is_quota_limit,
                            ),
                        )
                quota_replied_at = max((reply.replied_at for reply in replies if reply.is_quota_limit), default=None)
                if delivery is not None and delivery.posted_at is not None and quota_replied_at is not None:
                    run.quota_block_count += 1
                    if self.ai_catalogs is not None:
                        await self.ai_catalogs.record_quota_event(session, run.ai_catalog_id, quota_replied_at)
                    if run.state != PipelineRunState.BLOCKED:
                        await self.repo.create_delivery(
                            session,
                            ExecutionDelivery(
                                execution_attempt_id=attempt.id,
                                delivery_number=delivery.delivery_number + 1,
                                cause="quota",
                            ),
                        )
                        run.state = PipelineRunState.DISPATCHING
                    run.next_action_at = None
                    run.revision += 1
                    await session.flush()
                    return PipelineRunRead.model_validate(run)
                if delivery is not None and posted_at is not None and now - posted_at >= adapter.silent_timeout:
                    silent_retries = sum(
                        item.cause == "silent" for item in await self.repo.list_deliveries(session, attempt.id)
                    )
                    if silent_retries >= 1:
                        run.state = PipelineRunState.BLOCKED
                        run.pause_reason = adapter.silent_block_reason
                    else:
                        await self.repo.create_delivery(
                            session,
                            ExecutionDelivery(
                                execution_attempt_id=attempt.id,
                                delivery_number=delivery.delivery_number + 1,
                                cause="silent",
                            ),
                        )
                        run.state = PipelineRunState.DISPATCHING
                    run.next_action_at = None
                    run.revision += 1
                    await session.flush()
                    return PipelineRunRead.model_validate(run)
            # 2. If AWAITING_CI: Observe CI status
            elif run.state == PipelineRunState.AWAITING_CI and run.pull_number is not None:
                project_read = ProjectRead.model_validate(project)
                if project_read.github is None:
                    raise ProjectError(422, "Project missing GitHub connection for pipeline run")
                observation = await observer.observe(project_read.observation_config([run.pull_number]))
                pull_result = observation.pulls[0].result
                if pull_result.status == VerificationStatus.FAILED:
                    active_attempt = await self.repo.active_attempt(session, run.id)
                    # The observer exposes no failed job for a workflow-level
                    # failure (for example a runner/setup outage).  That is the
                    # only environment signal it can establish safely, so do
                    # not ask the agent to change application code in this case.
                    if not pull_result.unsuccessful_jobs:
                        run.state = PipelineRunState.PAUSED
                        run.pause_reason = "CI failed before a code job could be identified; inspect the environment"
                        run.next_action_at = None
                        run.revision += 1
                        if active_attempt is not None:
                            active_attempt.state = ExecutionAttemptState.FAILED
                            active_attempt.finished_at = now
                            active_attempt.failure_code = "CI_ENVIRONMENT_FAILURE"
                            active_attempt.failure_detail = pull_result.reason
                        await session.flush()
                        return PipelineRunRead.model_validate(run)
                    if not project_read.github.automation.auto_fix_ci:
                        run.state = PipelineRunState.PAUSED
                        run.pause_reason = "CI failed; automatic CI fixes are disabled for this project"
                        run.next_action_at = None
                        run.revision += 1
                        if active_attempt is not None:
                            active_attempt.state = ExecutionAttemptState.FAILED
                            active_attempt.finished_at = now
                            active_attempt.failure_code = "CI_FAILED"
                            active_attempt.failure_detail = pull_result.reason
                        await session.flush()
                        return PipelineRunRead.model_validate(run)
                    ci_fixes = [
                        attempt
                        for attempt in await self.repo.list_attempts(session, run.id)
                        if attempt.kind == "ci-fix" and attempt.epoch == run.epoch
                    ]
                    if len(ci_fixes) >= 2:
                        run.state = PipelineRunState.BLOCKED
                        run.pause_reason = "CI failed after two fix requests; resume manually"
                    elif active_attempt is not None:
                        active_attempt.state = ExecutionAttemptState.FAILED
                        active_attempt.finished_at = now
                        active_attempt.failure_code = "CI_FAILED"
                        active_attempt.failure_detail = pull_result.reason
                        prior = ImplementationRequest.model_validate(active_attempt.request_snapshot)
                        log_excerpt = await self._failed_job_log_excerpt(
                            project.github_connector_id,
                            project.github_repository,
                            observation.pulls[0].run,
                            pull_result.unsuccessful_jobs,
                        )
                        request = prior.model_copy(
                            update={
                                "kind": "ci-fix",
                                "correlation_marker": f"hub-attempt:{uuid4()}",
                                "pull_request": prior.pull_request.model_copy(
                                    update={"head_sha": observation.pulls[0].head_sha}
                                ),
                                "instructions": prior.instructions
                                + "\n\nCI failed for this PR. Fix these jobs: "
                                + ", ".join(pull_result.unsuccessful_jobs or [pull_result.reason])
                                + (f"\n\n## Bounded failing-job log excerpt\n\n{log_excerpt}" if log_excerpt else ""),
                            }
                        )
                        canonical = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
                        await self.repo.create_attempt(
                            session,
                            ExecutionAttempt(
                                pipeline_run_id=run.id,
                                attempt_number=await self.repo.next_attempt_number(session, run.id),
                                epoch=run.epoch,
                                kind=ExecutionAttemptKind.CI_FIX,
                                state=ExecutionAttemptState.PLANNED,
                                request_snapshot=request.model_dump(mode="json"),
                                request_digest=sha256(canonical.encode()).hexdigest(),
                                idempotency_key=UUID(request.correlation_marker.removeprefix("hub-attempt:")),
                            ),
                        )
                        run.state = PipelineRunState.DISPATCHING
                    run.revision += 1
                    await session.flush()
                elif pull_result.status == VerificationStatus.CLOSED:
                    pr = await observer.get_pull_request(
                        project.github_connector_id, project.github_repository, run.pull_number
                    )
                    if pr.get("state") == "closed":
                        await self._finish_closed_pull(session, run, pr, now)
                elif pull_result.status == VerificationStatus.PASSED:
                    if not project_read.github.automation.auto_merge:
                        run.state = PipelineRunState.PAUSED
                        run.pause_reason = "CI passed; automatic merge is disabled for this project"
                        run.next_action_at = None
                        run.revision += 1
                        active_attempt = await self.repo.active_attempt(session, run.id)
                        if active_attempt is not None:
                            active_attempt.state = ExecutionAttemptState.COMPLETED
                            active_attempt.finished_at = now
                        await session.flush()
                        return PipelineRunRead.model_validate(run)
                    # Re-observe immediately before the write; the merge API is
                    # still the final authority for branch rules and head SHA.
                    try:
                        token_value = await self.observer.get_token(project.github_connector_id, "github")
                        async with pipeline_services.create_github_client(token_value) as client:
                            reader = GitHubActionsReader(client)
                            current = await reader.observe_pull(
                                project_read.observation_config([run.pull_number]), run.pull_number
                            )
                            if current.result.status != VerificationStatus.PASSED:
                                return PipelineRunRead.model_validate(run)
                            merge = await reader.merge_pull_request(
                                project.github_repository,
                                run.pull_number,
                                current.head_sha,
                                project_read.github.automation.merge_method,
                            )
                    except PipelineConfigurationError as exc:
                        raise ProjectError(422, str(exc)) from None
                    except GitHubObservationError as exc:
                        if exc.status_code not in (405, 409):
                            raise ProjectError(502, str(exc)) from None
                        merge = {"merged": False, "message": str(exc)}

                    if merge.get("merged") is True:
                        run.state = PipelineRunState.COMPLETED
                        run.pause_reason = None
                        run.next_action_at = None
                        run.revision += 1
                        active_attempt = await self.repo.active_attempt(session, run.id)
                        if active_attempt is not None:
                            active_attempt.state = ExecutionAttemptState.COMPLETED
                            active_attempt.finished_at = now
                        await session.flush()
                    else:
                        conflicts = [
                            item
                            for item in await self.repo.list_attempts(session, run.id)
                            if item.kind == "conflict-fix" and item.epoch == run.epoch
                        ]
                        if not project_read.github.automation.auto_fix_conflicts:
                            run.state = PipelineRunState.PAUSED
                            run.pause_reason = "Merge failed; automatic conflict fixes are disabled for this project"
                            active_attempt = await self.repo.active_attempt(session, run.id)
                            if active_attempt is not None:
                                active_attempt.state = ExecutionAttemptState.FAILED
                                active_attempt.finished_at = now
                                active_attempt.failure_code = "MERGE_FAILED"
                                active_attempt.failure_detail = "GitHub could not merge the verified pull request"
                        elif len(conflicts) >= 1:
                            run.state = PipelineRunState.BLOCKED
                            run.pause_reason = "Merge conflict persisted after one fix request; resume manually"
                        else:
                            active_attempt = await self.repo.active_attempt(session, run.id)
                            if active_attempt is None:
                                raise ProjectError(409, "Pipeline run has no active attempt to revise")
                            active_attempt.state = ExecutionAttemptState.FAILED
                            active_attempt.finished_at = now
                            active_attempt.failure_code = "MERGE_CONFLICT"
                            active_attempt.failure_detail = "GitHub could not merge the verified pull request"
                            prior = ImplementationRequest.model_validate(active_attempt.request_snapshot)
                            request = prior.model_copy(
                                update={
                                    "kind": "conflict-fix",
                                    "correlation_marker": f"hub-attempt:{uuid4()}",
                                    "pull_request": prior.pull_request.model_copy(
                                        update={"head_sha": observation.pulls[0].head_sha}
                                    ),
                                    "instructions": prior.instructions
                                    + "\n\nThe pull request cannot be merged cleanly. Merge the current base branch into this branch, resolve conflicts, run checks, and push the result.",
                                }
                            )
                            canonical = json.dumps(
                                request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
                            )
                            await self.repo.create_attempt(
                                session,
                                ExecutionAttempt(
                                    pipeline_run_id=run.id,
                                    attempt_number=await self.repo.next_attempt_number(session, run.id),
                                    epoch=run.epoch,
                                    kind=ExecutionAttemptKind.CONFLICT_FIX,
                                    state=ExecutionAttemptState.PLANNED,
                                    request_snapshot=request.model_dump(mode="json"),
                                    request_digest=sha256(canonical.encode()).hexdigest(),
                                    idempotency_key=UUID(request.correlation_marker.removeprefix("hub-attempt:")),
                                ),
                            )
                            run.state = PipelineRunState.DISPATCHING
                        run.next_action_at = None
                        run.revision += 1
                        await session.flush()

            return PipelineRunRead.model_validate(run)

    async def _finish_closed_pull(self, session: AsyncSession, run: PipelineRun, pr: dict, now: datetime) -> None:
        merged = pr.get("merged") is True
        run.state = PipelineRunState.COMPLETED if merged else PipelineRunState.CANCELED
        run.pause_reason = None if merged else "Pull request was closed without a confirmed merge"
        run.next_action_at = None
        run.revision += 1
        attempt = await self.repo.active_attempt(session, run.id)
        if attempt is not None:
            attempt.state = ExecutionAttemptState.COMPLETED if merged else ExecutionAttemptState.FAILED
            attempt.finished_at = now
            attempt.failure_code = None if merged else "PR_CLOSED"
            attempt.failure_detail = run.pause_reason
        await session.flush()

    async def _block_for_project_change(
        self, session: AsyncSession, run: PipelineRun, now: datetime
    ) -> PipelineRunRead:
        """A run pinned to an outdated project can never progress: release its catalog capacity and surface it."""
        attempt = await self.repo.active_attempt(session, run.id)
        # A delivered or uncertain delivery may still be running at the agent; warn before a resume duplicates it.
        in_flight = run.state == PipelineRunState.IMPLEMENTING or (
            attempt is not None and attempt.state == ExecutionAttemptState.DISPATCHING
        )
        reason = PROJECT_CHANGED_BLOCK_REASON + (IN_FLIGHT_RESUME_WARNING if in_flight else "")
        run.state = PipelineRunState.BLOCKED
        run.pause_reason = reason
        run.next_action_at = None
        run.revision += 1
        if attempt is not None:
            attempt.state = ExecutionAttemptState.FAILED
            attempt.finished_at = now
            attempt.failure_code = "PROJECT_CHANGED"
            attempt.failure_detail = reason
        await session.flush()
        return PipelineRunRead.model_validate(run)

    async def _default_catalog(self, session: AsyncSession) -> AICatalog:
        """Return the seeded AI catalog; create it for metadata-only test databases."""
        catalogs = AICatalogRepository()
        catalog = await catalogs.get_by_key(session, "personal-codex", lock=True)
        if catalog is None:
            catalog = AICatalog(
                key="personal-codex",
                name="Personal Codex",
                kind=AICatalogKind.CODEX,
                adapter=CodexGithubMentionAdapter.key,
                enabled=True,
                availability_state=AICatalogState.NORMAL,
                revision=1,
            )
            session.add(catalog)
            await session.flush()
        return catalog

    async def dispatch_implementation(self, run_id: UUID, *, owner: str, token: UUID) -> PipelineRunRead:
        """Reconcile then make one delivery through the catalog's adapter, retaining state across uncertain writes."""
        now = datetime.now(UTC)
        async with AsyncTransaction() as session:
            run = await self.repo.get_leased(session, run_id, owner=owner, token=token, now=now)
            if run is None:
                await self._raise_lease_conflict(session, run_id, "dispatch implementation")
            if run.state != PipelineRunState.DISPATCHING:
                return PipelineRunRead.model_validate(run)
            if run.next_action_at is not None and _utc(run.next_action_at) > now:
                return PipelineRunRead.model_validate(run)
            project = await self.projects.get(session, run.project_id)
            if (
                not project.enabled
                or project.revision != run.project_revision
                or project.github_connector_id is None
                or project.github_repository is None
            ):
                # Checked before admission so a run that can never be delivered takes no catalog capacity.
                return await self._block_for_project_change(session, run, now)
            adapter = await resolve_execution_adapter(session, run.ai_catalog_id)
            attempt = await self.repo.active_attempt(session, run.id)
            if attempt is None:
                raise ProjectError(409, "Pipeline run has no active implementation attempt")
            delivery = await self.repo.latest_delivery(session, attempt.id)
            if delivery is None:
                delivery = await self.repo.create_delivery(
                    session,
                    ExecutionDelivery(
                        execution_attempt_id=attempt.id,
                        delivery_number=1,
                        cause="initial",
                    ),
                )
            elif delivery.comment_id is not None:
                delivery = await self.repo.create_delivery(
                    session,
                    ExecutionDelivery(
                        execution_attempt_id=attempt.id,
                        delivery_number=delivery.delivery_number + 1,
                        cause="resume",
                    ),
                )
            # The delivery is settled before admission so the catalog ledger counts it once, however often it retries.
            if self.ai_catalogs is not None:
                admission = await self.ai_catalogs.request_dispatch(
                    session, run.ai_catalog_id, run.id, f"delivery:{delivery.id}", now
                )
                if admission.rejection is not None:
                    # Keep what the policy recorded while rejecting, such as a hold it has just reached.
                    await session.commit()
                    raise ProjectError(409, admission.rejection)
            attempt.state = ExecutionAttemptState.DISPATCHING
            request = ImplementationRequest.model_validate(attempt.request_snapshot)
            target = DeliveryTarget(project.github_connector_id, project.github_repository, run.pull_number)
            expected_revision = run.revision

        # Do all adapter I/O outside the transaction. An uncertain delivery leaves the planned delivery
        # intact so the next tick reconciles it before attempting another write.
        try:
            await self._guard_dispatch(run_id, owner, token, expected_revision)
            async with asyncio.timeout(DISPATCH_IO_SECONDS):
                receipt = await adapter.deliver(
                    self.observer,
                    target,
                    request,
                    delivery.delivery_number,
                    authorize=lambda: self._guard_dispatch(run_id, owner, token, expected_revision),
                )
        except TimeoutError:
            raise ProjectError(504, "Delivery exceeded its time budget; reconcile on the next tick") from None
        except PipelineConfigurationError as exc:
            raise ProjectError(422, str(exc)) from None

        posted_at = receipt.posted_at
        async with AsyncTransaction() as session:
            run = await self.repo.get_leased(session, run_id, owner=owner, token=token, now=datetime.now(UTC))
            if run is None:
                await self._raise_lease_conflict(session, run_id, "record delivery")
            attempt = await self.repo.active_attempt(session, run.id)
            if attempt is None or attempt.id != delivery.execution_attempt_id:
                raise ProjectError(409, "Pipeline run changed during delivery")
            recorded = await self.repo.latest_delivery(session, attempt.id)
            if recorded is None or recorded.id != delivery.id:
                raise ProjectError(409, "Pipeline delivery changed during delivery")
            recorded.comment_id = receipt.external_id
            recorded.posted_at = posted_at
            attempt.state = ExecutionAttemptState.RUNNING
            attempt.external_correlation_id = receipt.external_id
            attempt.external_status = "delivered"
            attempt.conversation_url = receipt.url
            attempt.started_at = attempt.started_at or posted_at
            run.state = PipelineRunState.IMPLEMENTING
            run.next_action_at = None
            run.revision += 1
            if self.ai_catalogs is not None:
                await self.ai_catalogs.record_dispatch_delivered(session, run.ai_catalog_id, posted_at)
            await session.flush()
            return PipelineRunRead.model_validate(run)

    async def _guard_dispatch(self, run_id: UUID, owner: str, token: UUID, expected_revision: int) -> None:
        """Reserve a lease longer than the bounded I/O and recheck authorization before posting."""
        now = datetime.now(UTC)
        async with AsyncTransaction() as session:
            run = await self.repo.get_leased(session, run_id, owner=owner, token=token, now=now)
            if run is None:
                await self._raise_lease_conflict(session, run_id, "authorize delivery")
            if run.state != PipelineRunState.DISPATCHING or run.revision != expected_revision:
                raise ProjectError(409, "Pipeline run changed before delivery")
            project = await self.projects.get(session, run.project_id)
            if not project.enabled or project.revision != run.project_revision:
                raise ProjectError(409, "Project changed before delivery")
            if self.ai_catalogs is not None:
                await self.ai_catalogs.require_dispatchable(session, run.ai_catalog_id, now)
            now = datetime.now(UTC)
            renewed = await self.repo.renew_lease(
                session,
                run_id,
                owner=owner,
                token=token,
                now=now,
                expires_at=now + timedelta(seconds=DISPATCH_LEASE_SECONDS),
            )
            if renewed is None:
                await self._raise_lease_conflict(session, run_id, "reserve delivery time")

    async def manual_advance(self, run_id: UUID, observer: PipelineObservationService) -> PipelineRunRead:
        owner = f"manual:{uuid4().hex[:8]}"
        grant = await self.acquire_lease(run_id, LeaseRequest(owner=owner, ttl_seconds=60))
        try:
            run = await self.get(run_id)
            if run.state == PipelineRunState.QUEUED:
                await self.prepare_implementation(
                    run_id,
                    PrepareImplementationAttempt(
                        owner=owner,
                        token=grant.token,
                        expected_run_revision=grant.run_revision,
                    ),
                )
                run = await self.get(run_id)
            if run.state == PipelineRunState.DISPATCHING:
                return await self.dispatch_implementation(run_id, owner=owner, token=grant.token)
            return await self.advance_run(run_id, owner=owner, token=grant.token, observer=observer)
        finally:
            await self.release_lease(run_id, LeaseMutation(owner=owner, token=grant.token))

    async def pause_run(self, run_id: UUID, request: PauseRunRequest | None = None) -> PipelineRunRead:
        async with AsyncTransaction() as session:
            run = await self.repo.get(session, run_id)
            if run is None:
                raise ProjectError(404, "Pipeline run not found")
            if run.state in (PipelineRunState.COMPLETED, PipelineRunState.FAILED, PipelineRunState.CANCELED):
                raise ProjectError(422, f"Cannot pause a run in {run.state} state")
            run.state = PipelineRunState.PAUSED
            run.pause_reason = request.reason if request and request.reason else "Manually paused by user"
            run.lease_owner = None
            run.lease_token = None
            run.lease_expires_at = None
            run.revision += 1
            await session.flush()
            return PipelineRunRead.model_validate(run)

    async def resume_run(self, run_id: UUID) -> PipelineRunRead:
        async with AsyncTransaction() as session:
            run = await self.repo.get(session, run_id, lock=True)
            if run is None:
                raise ProjectError(404, "Pipeline run not found")
            if run.state not in (PipelineRunState.PAUSED, PipelineRunState.BLOCKED):
                raise ProjectError(
                    422, f"Cannot resume a run that is not paused or blocked (current state: {run.state})"
                )
            attempts = await self.repo.list_attempts(session, run.id)
            expected_revision = run.revision
            project = await self.projects.get(session, run.project_id)
            if not project.enabled:
                raise ProjectError(409, "Project is disabled; enable it before resuming")
            if project.github_connector_id is None or project.github_repository is None:
                raise ProjectError(422, "Project missing GitHub connection for pipeline run")
            if project.revision != run.project_revision and (
                run.github_repository != project.github_repository
                or run.github_connector_id != project.github_connector_id
            ):
                # Another repository can resolve the same PR number to a different pull request, and another account
                # can neither reconcile earlier mentions nor share this catalog's quota.
                raise ProjectError(409, GITHUB_BINDING_CHANGED_CONFLICT)
            project_revision = project.revision
            connector_id, repository, pull_number = (
                project.github_connector_id,
                project.github_repository,
                run.pull_number,
            )
            if attempts:
                previous = attempts[-1]
                prior = ImplementationRequest.model_validate(previous.request_snapshot)
                kind = previous.kind
            else:
                prior, _, _ = self._build_implementation_request(run, repository)
                kind = ExecutionAttemptKind.IMPLEMENTATION

        try:
            async with asyncio.timeout(DISPATCH_IO_SECONDS):
                pr = await self.observer.get_pull_request(connector_id, repository, pull_number)
            if pr.get("state") not in ("open", "closed"):
                raise ValueError("Missing pull request state")
            pull = prior.pull_request.model_copy(
                update={"head_sha": pr["head"]["sha"], "head_ref": pr["head"]["ref"], "base_ref": pr["base"]["ref"]}
            )
            if not pull.head_sha or not pull.head_ref or not pull.base_ref:
                raise ValueError("Missing pull request revision")
        except TimeoutError:
            raise ProjectError(504, "Pull request read exceeded its time budget") from None
        except (GitHubObservationError, PipelineConfigurationError):
            raise ProjectError(502, "Could not read the pull request before resuming") from None
        except (KeyError, TypeError, ValueError):
            raise ProjectError(502, "GitHub returned incomplete pull request data") from None

        async with AsyncTransaction() as session:
            run = await self.repo.get(session, run_id, lock=True)
            if run is None or run.revision != expected_revision:
                raise ProjectError(409, "Pipeline run changed while resuming; reload and retry")
            project = await self.projects.get(session, run.project_id)
            if not project.enabled or project.revision != project_revision:
                raise ProjectError(409, "Project changed while resuming; reload and retry")
            now = datetime.now(UTC)
            if pr["state"] == "closed":
                await self._finish_closed_pull(session, run, pr, now)
                return PipelineRunRead.model_validate(run)
            if pull.head_ref != run.branch:
                raise ProjectError(409, "Pull request branch changed; enroll it again")
            active = await self.repo.active_attempt(session, run.id)
            if active is not None:
                active.state = ExecutionAttemptState.FAILED
                active.finished_at = now
                active.failure_code = "USER_RESUMED"
                active.failure_detail = "Superseded by a user-initiated resume"
            run.epoch += 1
            key = uuid4()
            implementation = prior.model_copy(update={"correlation_marker": f"hub-attempt:{key}", "pull_request": pull})
            snapshot = implementation.model_dump(mode="json")
            canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
            attempt = await self.repo.create_attempt(
                session,
                ExecutionAttempt(
                    pipeline_run_id=run.id,
                    attempt_number=await self.repo.next_attempt_number(session, run.id),
                    epoch=run.epoch,
                    kind=kind,
                    state=ExecutionAttemptState.PLANNED,
                    request_snapshot=snapshot,
                    request_digest=sha256(canonical.encode()).hexdigest(),
                    idempotency_key=key,
                ),
            )
            await self.repo.create_delivery(
                session, ExecutionDelivery(execution_attempt_id=attempt.id, delivery_number=1, cause="resume")
            )
            run.state = PipelineRunState.DISPATCHING
            run.next_action_at = None
            run.pause_reason = None
            # The operator's resume accepts settings changes; later ticks follow the current project.
            run.project_revision = project_revision
            run.revision += 1
            await session.flush()
            return PipelineRunRead.model_validate(run)

    async def cancel_run(self, run_id: UUID) -> PipelineRunRead:
        now = datetime.now(UTC)
        async with AsyncTransaction() as session:
            run = await self.repo.get(session, run_id)
            if run is None:
                raise ProjectError(404, "Pipeline run not found")
            if run.state in (PipelineRunState.COMPLETED, PipelineRunState.FAILED, PipelineRunState.CANCELED):
                raise ProjectError(422, f"Cannot cancel a run in {run.state} state")
            run.state = PipelineRunState.CANCELED
            run.pause_reason = "Manually canceled"
            run.lease_owner = None
            run.lease_token = None
            run.lease_expires_at = None
            run.revision += 1
            active_attempt = await self.repo.active_attempt(session, run.id)
            if active_attempt is not None:
                active_attempt.state = ExecutionAttemptState.FAILED
                active_attempt.failure_code = "CANCELED"
                active_attempt.failure_detail = "Run was canceled"
                active_attempt.finished_at = now
            await session.flush()
            return PipelineRunRead.model_validate(run)

    async def attach_pr(self, run_id: UUID, request: AttachPRRequest) -> PipelineRunRead:
        async with AsyncTransaction() as session:
            run = await self.repo.get(session, run_id)
            if run is None:
                raise ProjectError(404, "Pipeline run not found")
            if run.state not in (PipelineRunState.QUEUED, PipelineRunState.DISPATCHING, PipelineRunState.IMPLEMENTING):
                raise ProjectError(422, f"Cannot attach PR to a run in {run.state} state")
            project = await self.projects.get(session, run.project_id)
            repo_name = project.github_repository or "repo"
            run.pull_number = request.pull_number
            run.pull_url = request.pull_url or f"https://github.com/{repo_name}/pull/{request.pull_number}"
            run.state = PipelineRunState.AWAITING_CI
            run.revision += 1
            active_attempt = await self.repo.active_attempt(session, run.id)
            if active_attempt is not None and active_attempt.state in (
                ExecutionAttemptState.PLANNED,
                ExecutionAttemptState.DISPATCHING,
            ):
                active_attempt.state = ExecutionAttemptState.RUNNING
            await session.flush()
            return PipelineRunRead.model_validate(run)

    async def complete_attempt(
        self, run_id: UUID, attempt_id: UUID, request: CompleteAttemptRequest
    ) -> ExecutionAttemptRead:
        now = datetime.now(UTC)
        async with AsyncTransaction() as session:
            run = await self.repo.get(session, run_id)
            if run is None:
                raise ProjectError(404, "Pipeline run not found")
            attempt = await self.repo.get_attempt(session, attempt_id)
            if attempt is None or attempt.pipeline_run_id != run_id:
                raise ProjectError(404, "Execution attempt not found for this pipeline run")
            if request.status == "completed":
                attempt.state = ExecutionAttemptState.COMPLETED
                attempt.finished_at = now
            else:
                attempt.state = ExecutionAttemptState.FAILED
                attempt.finished_at = now
                attempt.failure_code = request.failure_code or "WORKER_FAILED"
                attempt.failure_detail = request.failure_detail or "External worker reported failure"
                if run.state in (PipelineRunState.DISPATCHING, PipelineRunState.IMPLEMENTING):
                    run.state = PipelineRunState.FAILED
                    run.pause_reason = attempt.failure_detail
                    run.revision += 1
            await session.flush()
            return ExecutionAttemptRead.model_validate(attempt)

    async def _failed_job_log_excerpt(self, connector_id: UUID, repository: str, run, failed_names: list[str]) -> str:
        """Best-effort evidence for a fix request; log access never blocks state handling."""
        if run is None:
            return ""
        failed = [job for job in run.jobs if job.name in failed_names and job.conclusion == "failure"]
        if not failed:
            return ""
        try:
            token = await self.observer.get_token(connector_id, "github")
            async with pipeline_services.create_github_client(token) as client:
                reader = GitHubActionsReader(client)
                excerpts = []
                for job in failed[:3]:
                    excerpt = await reader.job_log_excerpt(repository, job.id, max_chars=1_000)
                    if excerpt:
                        excerpts.append(f"### {job.name}\n\n```text\n{excerpt}\n```")
                return "\n\n".join(excerpts)
        except (GitHubObservationError, PipelineConfigurationError):
            return ""

    @staticmethod
    def _github_repository(project) -> str:
        if project.github_repository is None:
            raise ProjectError(422, "Add a GitHub connection before preparing an implementation")
        return project.github_repository

    @staticmethod
    def _build_implementation_request(
        run: PipelineRun,
        repository: str,
        *,
        idempotency_key: UUID | None = None,
    ) -> tuple[ImplementationRequest, str, UUID]:
        idempotency_key = idempotency_key or uuid4()
        pull = PullRequestSnapshot.model_validate(run.pull_snapshot)
        instructions = (
            f"Implement pull request #{pull.number} in {repository} on its branch {pull.head_ref}. "
            "Follow the repository instructions, run the required checks, and push the result to that branch."
        )
        snapshot = ImplementationRequest(
            correlation_marker=f"hub-attempt:{idempotency_key}",
            repository=repository,
            pull_request=pull,
            instructions=instructions,
        )
        canonical = json.dumps(snapshot.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return snapshot, sha256(canonical.encode()).hexdigest(), idempotency_key
