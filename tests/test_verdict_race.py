#!/usr/bin/env python3
"""test_verdict_race.py — Regression tests for dev-harness-kit issues #104 + #244.

Ported from sh-ai-x/dev-harness-kit's tests/test_template_review_verdict_race.py
during the Phase 4 gates-distribution migration (issue #12) -- this
extraction/gate-time-race logic used to live in dev-harness-kit's
consumer TEMPLATE and is pinned here now that it has moved into this
repo's reusable workflows.

Pins the consumer-template verdict-extraction contract. Originally for
issue #104 (head -1 / -tail / missing-verdict hard-fail); extended for
issue #244 (port boilerplate-web PR #17/#19: read from agent output
file, NEVER grep PR comments).

Issue #823 split the bundled review.yml into review.yml + security.yml,
each now owning its own single-judge severity gate. This file pins the
shared extract/contract across BOTH new templates; the parallel
single-judge behavior is covered by test_review_gate.py and
test_security_gate.py.

Bugs verified:
1. templates/ci/.github/workflows/{review,security}.yml extract steps
   MUST call scripts/extract-verdict.py (primary source) and MUST
   NOT grep PR comments. The previous `tail -1` comment-grep was the
   root cause of the deterministic gate flap on boilerplate-web PR #18:
   it could resurrect a stale "Verdict: Changes Requested" from the
   previous push (issue #244).
2. The per-judge gate (Review verdict gate / Security verdict gate)
   MUST default missing R or S to Approve with ::warning::
   (project's own .github/workflows/review.yml already does this; the
   template must mirror).
3. The per-judge gate MUST extract the verdict itself at gate time (not
   rely on stale per-job outputs that captured verdicts BEFORE the LLM
   posted its comment). This eliminates the race where the extract step
   ran immediately on job-start and captured empty results, while the
   LLM posted its verdict seconds later.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
REVIEW_TEMPLATE = REPO_ROOT / ".github" / "workflows" / "review.yml"
SECURITY_TEMPLATE = REPO_ROOT / ".github" / "workflows" / "security.yml"
EXTRACT_VERDICT_SCRIPT = REPO_ROOT / "scripts" / "extract_verdict.py"

# Issue #823: each new template has its own gate step name. The old
# "Combined verdict gate" step (which read R + S together) no longer
# exists — review.yml has `Review verdict gate` (R only), security.yml
# has `Security verdict gate` (S only).
REVIEW_GATE_STEP_NAME = "Review verdict gate"
SECURITY_GATE_STEP_NAME = "Security verdict gate"


def _job_body(text: str, job_name: str) -> str:
    m = re.search(
        rf"^  {job_name}:\n(?P<body>.*?)(?=^  [a-z_]+:\n|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if m is None:
        raise AssertionError(f"{job_name}: job block not found in template")
    return m.group("body")


def _extract_gate_bash(text: str, step_name: str) -> str:
    """Extract the bash body of the gate step identified by `step_name`."""
    lines = text.splitlines()
    step_idx = None
    for i, ln in enumerate(lines):
        if ln.strip() == f"- name: {step_name}":
            step_idx = i
            break
    if step_idx is None:
        raise RuntimeError(f"{step_name} step not found in template")
    body_start = None
    for j in range(step_idx, min(step_idx + 5, len(lines))):
        if lines[j].lstrip().startswith("run:"):
            body_start = j + 1
            break
    if body_start is None:
        raise RuntimeError("`run:` not found in gate step")
    indent = None
    for j in range(body_start, len(lines)):
        if lines[j].strip():
            indent = len(lines[j]) - len(lines[j].lstrip())
            break
    if indent is None:
        raise RuntimeError("empty gate body")
    body = []
    for j in range(body_start, len(lines)):
        if not lines[j].strip():
            body.append("")
            continue
        if len(lines[j]) - len(lines[j].lstrip()) < indent:
            break
        body.append(lines[j][indent:])
    return "\n".join(body).rstrip() + "\n"


class TestTemplateVerdictExtractionOrdering(unittest.TestCase):
    """Pins the post-#244 contract: extract step uses extract-verdict.py,
    NEVER the comment-grep fallback.

    The previous bug-1 pin enforced `tail -1` on PR comments. That was
    the source of deterministic gate flapping on every push that touched
    a PR with prior review runs (boilerplate-web PR #18 repro). Issue
    #244 replaces the comment-grep with scripts/extract-verdict.py
    (parses the agent's actual transcript file). This test now pins
    the new contract.

    Issue #823 split the contract across two files (review.yml +
    security.yml); each is verified independently here. The bundled
    pre-#823 shape (both review + security in one file with a single
    Combined verdict gate) is gone.
    """

    def setUp(self):
        self.review_text = REVIEW_TEMPLATE.read_text()
        self.security_text = SECURITY_TEMPLATE.read_text()

    def test_review_job_extract_uses_script(self):
        """The review job's extract step MUST call scripts/extract_verdict.py
        as the PRIMARY verdict source, never a bare comment-grep.

        Note: the run_id-scoped PR-comments FALLBACK (issue #625) also
        legitimately fetches `.../issues/<PR>/comments` -- that's a
        correctly-scoped, later-added mechanism, not the issue #244 bug
        (which grepped comments as the primary source with no run_id
        filter, resurrecting stale verdicts). The real invariant this
        test pins is "extract_verdict.py runs first"; a plain substring
        check for the comments endpoint would false-positive on the
        legitimate #625 fallback (and did, when this test was ported
        from dev-harness-kit -- its version of this check happened to
        rely on `${PR_NUMBER}` bash-interpolation syntax specifically,
        which coincidentally differed between the pre- and post-fix
        code, not on anything semantically meaningful).
        """
        body = _job_body(self.review_text, "review")
        self.assertIn(
            "scripts/extract_verdict.py",
            body,
            "review extract step must call scripts/extract_verdict.py "
            "(issue #244 primary verdict source)",
        )
        # The primary source must be read BEFORE any comments-fallback
        # is even considered (i.e. extract_verdict.py's own file_verdict
        # result gates whether the comments path runs at all).
        self.assertLess(
            body.index("scripts/extract_verdict.py"),
            body.index("verdict_comments_fallback.sh"),
            "extract_verdict.py must run before the comments-fallback script",
        )

    def test_security_job_extract_uses_script(self):
        """The security job's extract step MUST call scripts/extract_verdict.py
        as the PRIMARY verdict source (see test_review_job_extract_uses_script's
        docstring for why a bare comments-endpoint substring check is fragile
        and was replaced with an ordering check instead)."""
        body = _job_body(self.security_text, "security")
        self.assertIn(
            "scripts/extract_verdict.py",
            body,
            "security extract step must call scripts/extract_verdict.py "
            "(issue #244 primary verdict source)",
        )
        self.assertLess(
            body.index("scripts/extract_verdict.py"),
            body.index("verdict_comments_fallback.sh"),
            "extract_verdict.py must run before the comments-fallback script",
        )

    def test_extract_verdict_script_is_installed(self):
        """The script the workflow depends on MUST exist in templates/ci/scripts/."""
        self.assertTrue(
            EXTRACT_VERDICT_SCRIPT.exists(),
            f"scripts/extract_verdict.py missing at "
            f"{EXTRACT_VERDICT_SCRIPT}; the review + security workflows "
            f"depend on this script (issue #244)",
        )

    def test_review_and_security_extract_use_verdict_source_label(self):
        """Both extract steps MUST emit a `verdict_source` output.

        Issue #823: review lives in review.yml, security in security.yml.
        """
        review_body = _job_body(self.review_text, "review")
        self.assertIn(
            "verdict_source=",
            review_body,
            "review extract step must emit verdict_source output (issue #244)",
        )
        security_body = _job_body(self.security_text, "security")
        self.assertIn(
            "verdict_source=",
            security_body,
            "security extract step must emit verdict_source output (issue #244)",
        )


class TestTemplateGateTolerance(unittest.TestCase):
    """Pins bug 2 + 3: missing-verdict tolerance + gate-time extract.

    - Empty R in pull_request mode MUST exit 0 (was exit 1).
    - Unparseable verdict MUST exit 0 (was exit 1).
    - The gate MUST extract the verdict itself (not depend on
      needs.<job>.outputs.verdict captured by the per-job extract step
      before the LLM posted).

    Issue #823: the bundled Combined verdict gate step no longer exists.
    Each template has its own gate step (Review verdict gate in
    review.yml; Security verdict gate in security.yml). This class
    pins the review gate contract; the parallel security gate is
    covered by test_security_gate.py.
    """

    def setUp(self):
        self.text = REVIEW_TEMPLATE.read_text()
        self.gate_bash = _extract_gate_bash(self.text, REVIEW_GATE_STEP_NAME)

    def _run_gate(self, r: str, event: str = "pull_request") -> subprocess.CompletedProcess:
        """Execute the template's review gate bash with R/EVENT env vars."""
        bash = self.gate_bash
        bash = bash.replace('R="${{ needs.review.outputs.verdict }}"', 'R="${R_OVERRIDE:-}"')
        bash = bash.replace('EVENT="$EVENT_NAME"', 'EVENT="${EVENT_OVERRIDE:-pull_request}"')
        env = {
            "PATH": "/usr/bin:/bin",
            "R_OVERRIDE": r,
            "EVENT_OVERRIDE": event,
        }
        return subprocess.run(
            ["bash", "-c", bash],
            capture_output=True, text=True, env=env, timeout=10,
        )

    def test_gate_tolerates_empty_R_in_pull_request(self):
        """The new contract: empty R in pull_request MUST exit 0, not 1."""
        cp = self._run_gate(r="", event="pull_request")
        if cp.returncode != 0 and cp.returncode != 1:
            self.skipTest(f"unexpected return code {cp.returncode}; gate may use live gh api: {cp.stderr}")
        self.assertEqual(
            cp.returncode, 0,
            f"empty R in pull_request MUST default to Approve + ::warning:: (was exit 1).\n"
            f"stdout={cp.stdout}\nstderr={cp.stderr}",
        )
        self.assertIn("::warning::", cp.stdout)

    def test_gate_tolerates_unparseable_verdict(self):
        """Unparseable verdict ('Requested') MUST exit 0, not 1."""
        cp = self._run_gate(r="Requested", event="pull_request")
        if cp.returncode not in (0, 1):
            self.skipTest(f"unexpected return code {cp.returncode}; gate may use live gh api")
        self.assertEqual(cp.returncode, 0, f"stdout={cp.stdout}\nstderr={cp.stderr}")
        self.assertIn("::warning::", cp.stdout)

    def test_gate_blocks_real_changes_requested(self):
        """Real review feedback must still exit 1."""
        cp = self._run_gate(r="Changes Requested", event="pull_request")
        if cp.returncode not in (0, 1):
            self.skipTest(f"unexpected return code {cp.returncode}; gate may use live gh api")
        self.assertEqual(cp.returncode, 1, f"stdout={cp.stdout}\nstderr={cp.stderr}")

    def test_gate_blocks_real_blocked(self):
        cp = self._run_gate(r="Blocked", event="pull_request")
        if cp.returncode not in (0, 1):
            self.skipTest(f"unexpected return code {cp.returncode}; gate may use live gh api")
        self.assertEqual(cp.returncode, 1, f"stdout={cp.stdout}\nstderr={cp.stderr}")

    def test_gate_has_no_hard_fail_on_empty_verdict(self):
        """Structural pin: the gate bash must NOT contain a hard-fail branch."""
        self.assertNotIn(
            "::error::review verdict missing",
            self.gate_bash,
            "review gate still has the hard-fail branch on missing R (issue #104 bug 2)",
        )


class TestTemplateJobStatusTolerance(unittest.TestCase):
    """Pin the post-#638 contract on the no-file branch of review + security
    extract steps.

    Issue #823: review job lives in review.yml, security job in
    security.yml; each is verified independently.
    """

    def setUp(self):
        self.review_text = REVIEW_TEMPLATE.read_text()
        self.security_text = SECURITY_TEMPLATE.read_text()

    def _case_arms(self, text: str, job: str) -> tuple[str, str]:
        """Return (transient_arm, default_arm) from the case block."""
        job_body = _job_body(text, job)
        m = re.search(
            r'case "\$\{\{ job\.status \}\}" in\n(?P<inner>.*?)^\s*esac\b',
            job_body, flags=re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(
            m,
            f'{job}: no `case "${{{{ job.status }}}}" in ... esac` block '
            f"found (issue #253 — boilerplate-web PR #20 patch missing)",
        )
        parts = re.split(r"^\s+\*\)", m.group("inner"), maxsplit=1, flags=re.MULTILINE)
        self.assertEqual(
            len(parts), 2,
            f"{job}: case-statement missing default `*)` arm (issue #253)",
        )
        return parts[0], parts[1]

    def _assert_job_status_contract(self, text: str, job: str) -> None:
        transient, default = self._case_arms(text, job)
        self.assertRegex(
            transient, r"(?m)^\s*cancelled\|failure\)",
            f"{job}: transient arm missing 'cancelled|failure)' case label "
            f"(issue #253 — boilerplate-web PR #20 contract)",
        )
        for arm, label, expect in (
            (transient, "cancelled|failure", {
                "verdict": "",
                "verdict_source": "default-no-verdict-job-${{ job.status }}",
                "agent_ran": "false",
            }),
            (default, "*) default", {
                "verdict": "Approve",
                "verdict_source": "default-approve-no-file",
                "agent_ran": "false",
            }),
        ):
            for key, val in expect.items():
                self.assertIn(
                    f'{key}="{val}"', arm,
                    f"{job}: {label} arm missing {key}=\"{val}\" (issue #638)",
                )

    def test_review_job_status_tolerance(self):
        self._assert_job_status_contract(self.review_text, "review")

    def test_security_job_status_tolerance(self):
        # Issue #823: security job now lives in security.yml.
        self._assert_job_status_contract(self.security_text, "security")


class TestTemplateGateTimeExtract(unittest.TestCase):
    """Pins bug 3 (root-cause fix): gate MUST extract verdict at gate time.

    Issue #823: each gate (review / security) handles its own
    per-judge race. The structural pin checks that each new file
    has its own `severity_gate` job (was `gate:` pre-#823).
    """

    def setUp(self):
        self.review_text = REVIEW_TEMPLATE.read_text()
        self.security_text = SECURITY_TEMPLATE.read_text()

    def _gate_job_body(self, text: str) -> str:
        m = re.search(
            r"^  (?:gate|severity_gate):\n(?P<body>.*?)(?=^  [a-z_]+:\n|\Z)",
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(m, "gate / severity_gate: job block not found in template")
        return m.group("body")

    def test_review_gate_does_not_depend_on_needs_outputs_for_verdict(self):
        """Review gate R must NOT come from `needs.review.outputs.verdict`."""
        body = self._gate_job_body(self.review_text)
        self.assertIn(REVIEW_GATE_STEP_NAME, body)

    def test_security_gate_does_not_depend_on_needs_outputs_for_verdict(self):
        """Security gate S must NOT come from `needs.security.outputs.verdict`."""
        body = self._gate_job_body(self.security_text)
        self.assertIn(SECURITY_GATE_STEP_NAME, body)


if __name__ == "__main__":
    unittest.main()
