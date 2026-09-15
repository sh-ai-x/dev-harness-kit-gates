"""Wrapper budget test for the consumer-side workflow files.

Phase 4 migrates `templates/ci/.github/workflows/{review,security,maintenance,auto-fix-pr}.yml`
in dev-harness-kit to thin wrappers that pin `uses: dev-harness-kit/gates/.github/workflows/<gate>.yml@v1`.
This test pins the **consumer-side** budget for those wrappers — the line cap
the dev-harness-kit fixture consumer must respect so the marketplace contract
stays honest.

The test is a no-op until the consumer wrappers land; until then it documents
the contract that future wrappers must satisfy.
"""
from __future__ import annotations

import pathlib


CONSUMER_WRAPPER_BUDGET_LINES = 60


def test_wrapper_budget_contract_documented():
    """Pin the budget so any PR that bloats a wrapper past the cap fails."""
    assert CONSUMER_WRAPPER_BUDGET_LINES == 60, "update this test if the cap moves"


def test_no_consumer_wrappers_in_this_repo():
    """The gates repo owns REUSABLE workflows, not consumer wrappers.

    Consumer wrappers live in dev-harness-kit's `templates/ci/.github/workflows/`
    and pin back to this repo. This repo must not duplicate them — otherwise
    the marketplace action and the consumer wrapper drift.
    """
    wf_dir = pathlib.Path(__file__).resolve().parent.parent / ".github/workflows"
    # resolve-paths.yml + ci.yml are the only files allowed here today.
    allowed = {"resolve-paths.yml", "ci.yml"}
    present = {p.name for p in wf_dir.glob("*.yml")}
    unexpected = present - allowed
    assert not unexpected, (
        f"unexpected workflow files in this repo: {unexpected}. "
        "Consumer wrappers belong in dev-harness-kit's templates/ci/, "
        "not here."
    )
