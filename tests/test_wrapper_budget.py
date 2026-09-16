"""Wrapper budget test for the gates repo.

Phase 4 promoted this test from a stub to a real check. It now:

  1. Allows the Phase 4 reusable workflows (review.yml / security.yml /
     maintenance.yml) under .github/workflows/ alongside the Phase 3
     pair (resolve-paths.yml / ci.yml).
  2. Pins a per-workflow line cap so any future bloat trips CI.
  3. Asserts action.yml does NOT attempt to invoke a reusable workflow
     from a composite step (invalid GH Actions syntax -- see
     test_judge_workflow_shape.py's module docstring for the full
     explanation of why action.yml cannot orchestrate the judges).
"""
from __future__ import annotations

import pathlib

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WF_DIR = REPO_ROOT / ".github/workflows"
ACTION_FILE = REPO_ROOT / "action.yml"

# Phase 3 + Phase 4 reusable workflows live in this repo. Consumer
# wrappers belong in dev-harness-kit's `templates/ci/.github/workflows/`
# and pin back to this repo via job-level
# `uses: sh-ai-x/dev-harness-kit-gates/.github/workflows/<gate>.yml@v1`.
ALLOWED_WORKFLOW_FILES = {
    "resolve-paths.yml",
    "ci.yml",
    "review.yml",
    "security.yml",
    "maintenance.yml",
}

# Per-workflow line cap. Source review.yml in dev-harness-kit is 674
# lines; the migrated version trims to under this cap.
WORKFLOW_LINE_CAP = 800


def test_only_allowed_workflow_files_in_this_repo():
    """The gates repo owns reusable workflows, not consumer wrappers."""
    present = {p.name for p in WF_DIR.glob("*.yml")}
    unexpected = present - ALLOWED_WORKFLOW_FILES
    assert not unexpected, (
        f"unexpected workflow files in this repo: {unexpected}. "
        "Consumer wrappers belong in dev-harness-kit's templates/ci/, "
        "not here."
    )


def test_workflow_line_cap():
    """No reusable workflow exceeds the line cap (keeps the marketplace
    contract honest — a bloated workflow is a code-smell signal)."""
    offenders = []
    for name in sorted(ALLOWED_WORKFLOW_FILES):
        path = WF_DIR / name
        if not path.exists():
            continue
        line_count = sum(1 for _ in path.read_text().splitlines())
        if line_count > WORKFLOW_LINE_CAP:
            offenders.append(f"{name}: {line_count} lines > cap {WORKFLOW_LINE_CAP}")
    assert not offenders, "workflows over the line cap: " + "; ".join(offenders)


def test_action_yml_does_not_uses_reusable_workflows():
    """action.yml (a composite action) must never `uses:` a
    .github/workflows/*.yml path -- that syntax is invalid for composite
    action steps (only job-level `uses:` can invoke a reusable workflow).
    See test_judge_workflow_shape.py for the full design rationale.
    """
    action = yaml.safe_load(ACTION_FILE.read_text())
    for step in action["runs"]["steps"]:
        uses = step.get("uses", "")
        assert not uses.startswith("./.github/workflows/"), (
            f"action.yml step {step.get('name')!r} uses={uses!r}: invalid — "
            "composite steps cannot invoke reusable workflow files"
        )
