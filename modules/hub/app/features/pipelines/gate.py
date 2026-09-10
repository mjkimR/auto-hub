"""Pure verification decisions. A passed observation never authorizes a merge."""

from app.features.pipelines.schemas import (
    RunSnapshot,
    VerificationConfig,
    VerificationResult,
    VerificationStatus,
)


def evaluate_verification(config: VerificationConfig, head_sha: str, run: RunSnapshot | None) -> VerificationResult:
    if run is None or run.head_sha != head_sha:
        return VerificationResult(status=VerificationStatus.WAITING, reason="No workflow run for the current PR head")

    if run.status != "completed":
        return VerificationResult(status=VerificationStatus.WAITING, reason="Workflow is not completed")

    # A setup failure or an unlisted failing job must not be hidden by successful required jobs.
    if run.conclusion == "failure":
        return VerificationResult(
            status=VerificationStatus.FAILED,
            reason="Workflow failed",
            unsuccessful_jobs=[job.name for job in run.jobs if job.conclusion == "failure"],
        )
    if run.conclusion != "success":
        return VerificationResult(status=VerificationStatus.BLOCKED, reason="Workflow did not complete successfully")

    jobs_by_name = {job.name: job for job in run.jobs}
    missing = [name for name in config.required_jobs if name not in jobs_by_name]
    if missing:
        return VerificationResult(
            status=VerificationStatus.BLOCKED, reason="Required jobs are missing", missing_jobs=missing
        )
    if any(sum(job.name == name for job in run.jobs) != 1 for name in config.required_jobs):
        return VerificationResult(status=VerificationStatus.BLOCKED, reason="Required job names are ambiguous")

    unsuccessful = [
        name
        for name in config.required_jobs
        if jobs_by_name[name].status != "completed" or jobs_by_name[name].conclusion != "success"
    ]
    if unsuccessful:
        return VerificationResult(
            status=VerificationStatus.BLOCKED,
            reason="Required jobs have not all succeeded",
            unsuccessful_jobs=unsuccessful,
        )
    return VerificationResult(status=VerificationStatus.PASSED, reason="Workflow and all required jobs succeeded")
