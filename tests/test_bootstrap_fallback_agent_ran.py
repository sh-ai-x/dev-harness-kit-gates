"""test_bootstrap_fallback_agent_ran.py — pin dev-harness-kit issue #219 Bug 2.

The bootstrap-PR fallback branch (triggered when
`anthropics/claude-code-action@v1`'s workflow-validation guard skips
the agent because the PR modifies `.github/workflows/*`) must report
`agent_ran=false`, not `agent_ran=true`. The fallback's `gh pr comment`
is a synthesized placeholder verdict, NOT a real agent review — if it
were reported as `agent_ran=true`, the severity gate's `agent_ran=false
-> exit 1` hard-fail (the install-broken detector) would be silently
defeated on every bootstrap PR.

This invariant used to be pinned in dev-harness-kit's own test suite
(tests/test_ci_setup.py) against the CONSUMER TEMPLATE before the
Phase 4 migration moved the actual bootstrap-fallback bash into this
repo's reusable workflows. Re-pinned here so the coverage isn't lost.
"""
from __future__ import annotations

import pathlib
import re

import pytest


WORKFLOWS_DIR = pathlib.Path(__file__).resolve().parent.parent / ".github/workflows"

# Both review.yml and security.yml have their own bootstrap-fallback
# branch (maintenance.yml does not use pull_request's workflow-
# validation-skip fallback pattern -- it has a different bump-PR /
# author-association gating mechanism instead).
FALLBACK_WORKFLOWS = (WORKFLOWS_DIR / "review.yml", WORKFLOWS_DIR / "security.yml")

NEEDS_FALLBACK_BRANCH_RE = re.compile(
    r'if \[ "\$\{\{ steps\.fallback\.outputs\.needs_fallback \}\}" = "true" \]; then'
    r'.*?fi',
    re.DOTALL,
)


@pytest.mark.parametrize("wf_path", FALLBACK_WORKFLOWS)
def test_bootstrap_fallback_branch_exists(wf_path):
    text = wf_path.read_text()
    branches = NEEDS_FALLBACK_BRANCH_RE.findall(text)
    assert branches, (
        f"{wf_path.name}: no bootstrap-fallback branch found — "
        "test invariant changed or the fallback logic was removed"
    )


@pytest.mark.parametrize("wf_path", FALLBACK_WORKFLOWS)
def test_bootstrap_fallback_reports_agent_ran_false(wf_path):
    """Issue #219 Bug 2: every `needs_fallback == 'true'` branch must
    write `agent_ran=false`, never `agent_ran=true`."""
    text = wf_path.read_text()
    branches = NEEDS_FALLBACK_BRANCH_RE.findall(text)
    assert branches, f"{wf_path.name}: no bootstrap-fallback branch found"
    bad = []
    for i, body in enumerate(branches):
        if re.search(r'echo "agent_ran=true" >> "\$GITHUB_OUTPUT"', body):
            bad.append(i)
        if not re.search(r'echo "agent_ran=false" >> "\$GITHUB_OUTPUT"', body):
            bad.append(i)
    assert not bad, (
        f"{wf_path.name}: bootstrap-fallback branch(es) {bad} do not "
        "correctly write `agent_ran=false` -- issue #219 Bug 2 regression"
    )
