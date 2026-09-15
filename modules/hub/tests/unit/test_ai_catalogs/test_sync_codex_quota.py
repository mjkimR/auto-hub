import runpy
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
blocking_reset = runpy.run_path(str(Path(__file__).resolve().parents[5] / "scripts/sync-codex-quota.py"))[
    "blocking_reset"
]


def bucket(primary=None, secondary=None):
    return {
        "limitId": "codex",
        "limitName": None,
        "primary": primary,
        "secondary": secondary,
        "planType": "pro",
        "credits": {"balance": "0"},
    }


@pytest.mark.parametrize("key", ["primary", "secondary"])
def test_only_windows_are_parsed(key):
    snapshot = bucket(**{key: {"usedPercent": 100, "resetsAt": 2_000_000_000}})
    assert blocking_reset({"rateLimitsByLimitId": {"codex": snapshot}}) == 2_000_000_000


def test_legacy_bucket_is_supported_when_map_is_null():
    snapshot = bucket(primary={"usedPercent": 100, "resetsAt": 2_000_000_000})
    assert blocking_reset({"rateLimitsByLimitId": None, "rateLimits": snapshot}) == 2_000_000_000


@pytest.mark.parametrize(
    "snapshot",
    [
        bucket(),
        bucket(primary={"usedPercent": 50, "resetsAt": 2_000_000_000}),
        bucket(primary={"usedPercent": 100, "resetsAt": None}),
        bucket(
            primary={"usedPercent": 100, "resetsAt": 2_000_000_000},
            secondary={"usedPercent": 100, "resetsAt": 2_000_000_001},
        ),
        bucket(primary="bad"),
    ],
)
def test_ambiguous_or_invalid_quota_fails_closed(snapshot):
    with pytest.raises(RuntimeError):
        blocking_reset({"rateLimitsByLimitId": {"codex": snapshot}})


def test_missing_codex_bucket_does_not_use_another_bucket():
    with pytest.raises(RuntimeError):
        blocking_reset(
            {"rateLimitsByLimitId": {"other": bucket(primary={"usedPercent": 100, "resetsAt": 2_000_000_000})}}
        )
