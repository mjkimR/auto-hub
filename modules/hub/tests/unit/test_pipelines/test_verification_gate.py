import pytest
from app.features.project_management.pipelines.gate import evaluate_verification
from app.features.project_management.pipelines.schemas import JobSnapshot, RunSnapshot, VerificationConfig

pytestmark = pytest.mark.unit


def make_run(**overrides) -> RunSnapshot:
    return RunSnapshot.model_validate(
        {
            "id": 10,
            "attempt": 1,
            "head_sha": "a" * 40,
            "status": "completed",
            "conclusion": "success",
            "url": "https://github.com/owner/app/actions/runs/10",
            "jobs": [{"name": name, "status": "completed", "conclusion": "success"} for name in ("lint", "test")],
            **overrides,
        }
    )


class TestVerificationGate:
    config = VerificationConfig(workflow="ci.yml", required_jobs=["lint", "test"])

    async def test_all_required_jobs_and_workflow_must_succeed(self):
        assert evaluate_verification(self.config, "a" * 40, make_run()).status == "passed"

    @pytest.mark.parametrize("run", [None, make_run(head_sha="b" * 40)])
    async def test_missing_or_old_head_never_passes(self, run):
        assert evaluate_verification(self.config, "a" * 40, run).status == "waiting"

    @pytest.mark.parametrize("status", ["queued", "in_progress", "waiting", "requested"])
    async def test_pending_run_cannot_reuse_success(self, status):
        assert evaluate_verification(self.config, "a" * 40, make_run(status=status)).status == "waiting"

    @pytest.mark.parametrize("conclusion", ["skipped", "neutral", "cancelled", "timed_out", "action_required", None])
    async def test_unsuccessful_workflow_is_blocked(self, conclusion):
        result = evaluate_verification(self.config, "a" * 40, make_run(conclusion=conclusion))
        assert result.status == "blocked"

    async def test_unlisted_failing_job_still_fails_workflow(self):
        run = make_run(conclusion="failure")
        run.jobs.append(JobSnapshot(name="setup", status="completed", conclusion="failure"))
        result = evaluate_verification(self.config, "a" * 40, run)
        assert result.status == "failed"
        assert result.unsuccessful_jobs == ["setup"]

    async def test_one_success_does_not_hide_missing_required_job(self):
        run = make_run()
        run.jobs.pop()
        result = evaluate_verification(self.config, "a" * 40, run)
        assert result.status == "blocked"
        assert result.missing_jobs == ["test"]

    @pytest.mark.parametrize("conclusion", ["skipped", "neutral", "failure", "cancelled", None])
    async def test_workflow_success_does_not_hide_unsuccessful_required_job(self, conclusion):
        run = make_run()
        run.jobs[1].conclusion = conclusion
        result = evaluate_verification(self.config, "a" * 40, run)
        assert result.status == "blocked"
        assert result.unsuccessful_jobs == ["test"]

    async def test_duplicate_required_job_names_are_ambiguous(self):
        run = make_run()
        run.jobs.append(run.jobs[0])
        assert evaluate_verification(self.config, "a" * 40, run).status == "blocked"
