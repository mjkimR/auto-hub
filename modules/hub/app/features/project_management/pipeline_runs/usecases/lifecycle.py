from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Annotated, Never
from uuid import UUID, uuid4

from app.features.project_management.pipeline_runs.dispatch import (
    CODEX_CONNECTOR_LOGIN,
    build_codex_mention_comment,
    is_codex_quota_reply,
)
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

ACTIVE_RUN_CONFLICT = "This project already has an active pipeline run"


class PipelineRunUseCase:
    def __init__(
        self,
        repo: Annotated[PipelineRunRepository, Depends()],
        projects: Annotated[ProjectService, Depends()],
        observer: Annotated[PipelineObservationService, Depends()],
    ):
        self.repo = repo
        self.projects = projects
        self.observer = observer

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
            if await self.repo.get_active(session, project_id) is not None:
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
                if await self.repo.get_active(session, project_id, lock=True) is not None:
                    raise ProjectError(409, ACTIVE_RUN_CONFLICT)
                run = await self.repo.create(
                    session,
                    PipelineRun(
                        project_id=project_id,
                        project_revision=project.revision,
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
            if not project.enabled or project.revision != run.project_revision:
                raise ProjectError(409, "Project changed after this pipeline run was acquired")
            if project.github_repository is None or project.github_connector_id is None:
                raise ProjectError(422, "Project missing GitHub connection for pipeline run")

            # A planned delivery must be reconciled or posted before a run can advance.
            if run.state == PipelineRunState.IMPLEMENTING:
                comments = await observer.list_pull_comments(
                    project.github_connector_id, project.github_repository, run.pull_number
                )
                attempt = await self.repo.active_attempt(session, run.id)
                if attempt is None:
                    raise ProjectError(409, "Pipeline run has no active implementation attempt")
                delivery = await self.repo.latest_delivery(session, attempt.id)
                quota_reply = False
                if delivery is not None and delivery.posted_at is not None:
                    for comment in comments:
                        author = comment.get("user", {}).get("login")
                        comment_id = comment.get("id")
                        created_at = comment.get("created_at", "")
                        if (
                            author != CODEX_CONNECTOR_LOGIN
                            or not isinstance(created_at, str)
                            or created_at < delivery.posted_at.isoformat()
                        ):
                            continue
                        quota = is_codex_quota_reply(author, comment.get("body"))
                        quota_reply = quota_reply or quota
                        if comment_id is None:
                            continue
                        if not await self.repo.has_reply_comment(session, str(comment_id)):
                            await self.repo.create_reply(
                                session,
                                ExecutionReply(
                                    execution_attempt_id=attempt.id,
                                    comment_id=str(comment_id),
                                    author=author,
                                    replied_at=datetime.fromisoformat(created_at.replace("Z", "+00:00")),
                                    excerpt=(str(comment.get("body") or "").strip()[:500] or None),
                                    is_quota_limit=quota,
                                ),
                            )
                if delivery is not None and delivery.posted_at is not None and quota_reply:
                    quota_retries = sum(
                        item.cause == "quota" for item in await self.repo.list_deliveries(session, attempt.id)
                    )
                    if quota_retries >= 2:
                        run.state = PipelineRunState.BLOCKED
                        run.pause_reason = "Codex usage limit persisted after two retries; resume manually after reset"
                        run.next_action_at = None
                    else:
                        await self.repo.create_delivery(
                            session,
                            ExecutionDelivery(
                                execution_attempt_id=attempt.id,
                                delivery_number=delivery.delivery_number + 1,
                                cause="quota",
                            ),
                        )
                        run.state = PipelineRunState.DISPATCHING
                        run.next_action_at = now + timedelta(hours=5, minutes=10)
                    run.revision += 1
                    await session.flush()
                    return PipelineRunRead.model_validate(run)
                if (
                    delivery is not None
                    and delivery.posted_at is not None
                    and now - delivery.posted_at >= timedelta(hours=2, minutes=5)
                ):
                    silent_retries = sum(
                        item.cause == "silent" for item in await self.repo.list_deliveries(session, attempt.id)
                    )
                    if silent_retries >= 1:
                        run.state = PipelineRunState.BLOCKED
                        run.pause_reason = "Codex did not push after a silent retry; resume manually"
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
                pr = await observer.find_pull_request(
                    project.github_connector_id, project.github_repository, run.branch
                )
                delivery_head = PullRequestSnapshot.model_validate(attempt.request_snapshot["pull_request"]).head_sha
                if pr is not None and pr.get("head", {}).get("sha") != delivery_head:
                    run.state = PipelineRunState.AWAITING_CI
                    run.revision += 1
                    active_attempt = await self.repo.active_attempt(session, run.id)
                    if active_attempt is not None:
                        active_attempt.state = ExecutionAttemptState.RUNNING
                    await session.flush()

            # 2. If AWAITING_CI: Observe CI status
            elif run.state == PipelineRunState.AWAITING_CI and run.pull_number is not None:
                project_read = ProjectRead.model_validate(project)
                observation = await observer.observe(project_read.observation_config([run.pull_number]))
                pull_result = observation.pulls[0].result
                if pull_result.status == VerificationStatus.FAILED:
                    active_attempt = await self.repo.active_attempt(session, run.id)
                    # The observer exposes no failed job for a workflow-level
                    # failure (for example a runner/setup outage).  That is the
                    # only environment signal it can establish safely, so do
                    # not ask Codex to change application code in this case.
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
                    ci_fixes = [
                        attempt
                        for attempt in await self.repo.list_attempts(session, run.id)
                        if attempt.kind == "ci-fix" and attempt.epoch == run.epoch
                    ]
                    if len(ci_fixes) >= 2:
                        run.state = PipelineRunState.BLOCKED
                        run.pause_reason = "CI failed after two Codex fix requests; resume manually"
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
                    run.state = PipelineRunState.CANCELED
                    run.pause_reason = "Pull request was closed without a confirmed merge"
                    run.revision += 1
                    active_attempt = await self.repo.active_attempt(session, run.id)
                    if active_attempt is not None:
                        active_attempt.state = ExecutionAttemptState.FAILED
                        active_attempt.finished_at = now
                        active_attempt.failure_code = "PR_CLOSED"
                        active_attempt.failure_detail = run.pause_reason
                    await session.flush()
                elif pull_result.status == VerificationStatus.PASSED:
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
                                project.github_repository, run.pull_number, current.head_sha
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
                        if len(conflicts) >= 1:
                            run.state = PipelineRunState.BLOCKED
                            run.pause_reason = "Merge conflict persisted after one Codex fix request; resume manually"
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

    async def dispatch_implementation(self, run_id: UUID, *, owner: str, token: UUID) -> PipelineRunRead:
        """Reconcile then post one initial mention, retaining state across uncertain writes."""
        now = datetime.now(UTC)
        async with AsyncTransaction() as session:
            run = await self.repo.get_leased(session, run_id, owner=owner, token=token, now=now)
            if run is None:
                await self._raise_lease_conflict(session, run_id, "dispatch implementation")
            if run.state != PipelineRunState.DISPATCHING:
                return PipelineRunRead.model_validate(run)
            project = await self.projects.get(session, run.project_id)
            if not project.enabled or project.revision != run.project_revision:
                raise ProjectError(409, "Project changed after this pipeline run was enrolled")
            if project.github_connector_id is None or project.github_repository is None:
                raise ProjectError(422, "Project missing GitHub connection for pipeline run")
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
            attempt.state = ExecutionAttemptState.DISPATCHING
            request = ImplementationRequest.model_validate(attempt.request_snapshot)
            connector_id, repository, pull_number = (
                project.github_connector_id,
                project.github_repository,
                run.pull_number,
            )

        # Do all GitHub I/O outside the transaction. An uncertain post leaves the planned delivery
        # intact so the next tick reconciles the marker before attempting another write.
        try:
            auth_token = await self.observer.get_token(connector_id, "github")
            async with pipeline_services.create_github_client(auth_token) as client:
                reader = GitHubActionsReader(client)
                login = await reader.current_login()
                marker = f"{request.correlation_marker} kind={request.kind} delivery={delivery.delivery_number}"
                comment = await reader.reconcile_issue_comment(repository, pull_number, marker, login)
                if comment is None:
                    comment = await reader.post_issue_comment(
                        repository,
                        pull_number,
                        build_codex_mention_comment(request, delivery=delivery.delivery_number),
                    )
        except PipelineConfigurationError as exc:
            raise ProjectError(422, str(exc)) from None

        comment_id = comment.get("id")
        if comment_id is None:
            raise ProjectError(502, "GitHub mention delivery returned an incomplete comment")
        async with AsyncTransaction() as session:
            run = await self.repo.get_leased(session, run_id, owner=owner, token=token, now=datetime.now(UTC))
            if run is None:
                await self._raise_lease_conflict(session, run_id, "record mention delivery")
            attempt = await self.repo.active_attempt(session, run.id)
            if attempt is None or attempt.id != delivery.execution_attempt_id:
                raise ProjectError(409, "Pipeline run changed during mention delivery")
            recorded = await self.repo.latest_delivery(session, attempt.id)
            if recorded is None or recorded.id != delivery.id:
                raise ProjectError(409, "Pipeline delivery changed during mention delivery")
            recorded.comment_id = str(comment_id)
            recorded.posted_at = now
            attempt.state = ExecutionAttemptState.RUNNING
            attempt.external_correlation_id = str(comment_id)
            attempt.external_status = "delivered"
            attempt.conversation_url = str(comment.get("html_url")) if comment.get("html_url") else None
            attempt.started_at = now
            run.state = PipelineRunState.IMPLEMENTING
            run.next_action_at = None
            run.revision += 1
            await session.flush()
            return PipelineRunRead.model_validate(run)

    async def manual_advance(self, run_id: UUID, observer: PipelineObservationService) -> PipelineRunRead:
        owner = f"manual:{uuid4().hex[:8]}"
        grant = await self.acquire_lease(run_id, LeaseRequest(owner=owner, ttl_seconds=60))
        try:
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
            run = await self.repo.get(session, run_id)
            if run is None:
                raise ProjectError(404, "Pipeline run not found")
            if run.state not in (PipelineRunState.PAUSED, PipelineRunState.BLOCKED):
                raise ProjectError(
                    422, f"Cannot resume a run that is not paused or blocked (current state: {run.state})"
                )
            # A user resume is an explicit request to deliver another mention;
            # dispatch_implementation records it with cause=resume.
            run.state = PipelineRunState.DISPATCHING
            run.next_action_at = None
            run.pause_reason = None
            run.epoch += 1
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
