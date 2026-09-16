"""Pin the shape of the composite action (action.yml) and the post-verdict-audit
composite action (.github/actions/post-verdict-audit/action.yml).

Companion to test_workflow_call_inputs.py (which pins each reusable workflow
individually).

IMPORTANT design constraint this file pins: a composite action's
`runs.steps[].uses:` can only reference another ACTION, never a reusable
WORKFLOW file (.github/workflows/*.yml) -- GitHub Actions has no mechanism
for a composite action to invoke a reusable workflow. An earlier revision
of action.yml attempted `uses: ./.github/workflows/review.yml` etc. inside
its composite steps, which is invalid syntax that would fail at the
action-resolution step. action.yml is therefore scoped to ONLY the
path-rule resolution (mirroring resolve-paths.yml, inlined since even that
reusable workflow cannot be `uses:`-called from a composite step) -- it
does not and cannot orchestrate the judge workflows. Consumers invoke each
judge directly via job-level `uses:` in their own workflow file (see
README.md's "Consumer examples").
"""
from __future__ import annotations

import pathlib

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ACTION_FILE = REPO_ROOT / "action.yml"
POST_AUDIT_FILE = REPO_ROOT / ".github/actions/post-verdict-audit/action.yml"


# ---------------------------------------------------------------------------
# action.yml — resolve-only composite action
# ---------------------------------------------------------------------------


def _load_action() -> dict:
    return yaml.safe_load(ACTION_FILE.read_text())


def test_action_is_composite():
    assert _load_action()["runs"]["using"] == "composite"


def test_action_inputs_present():
    inputs = _load_action()["inputs"]
    for name in ("gates_json_b64", "provider", "model", "output_artifact"):
        assert name in inputs, f"action.yml: input {name} missing"
    assert inputs["gates_json_b64"]["required"] is True


def test_action_outputs_present():
    outputs = _load_action()["outputs"]
    for name in ("review", "security", "maintenance", "rule_warnings"):
        assert name in outputs, f"action.yml: output {name} missing"


def test_action_does_not_attempt_to_invoke_reusable_workflows():
    """No composite step may `uses:` a .github/workflows/*.yml path -- that
    syntax is invalid for composite actions and would fail at runtime with
    an action-resolution error, not a YAML parse error (so a plain YAML
    validity check would never catch it)."""
    steps = _load_action()["runs"]["steps"]
    for step in steps:
        uses = step.get("uses", "")
        assert not uses.startswith("./.github/workflows/"), (
            f"action.yml step {step.get('name')!r}: `uses: {uses}` references a "
            "reusable workflow file, which is invalid inside a composite action "
            "(composite steps can only `uses:` another action)"
        )


def test_action_steps_only_uses_real_actions():
    """Every `uses:` in action.yml must reference a genuine action (a pinned
    external action ref like `owner/repo@version`), never a workflow file."""
    steps = _load_action()["runs"]["steps"]
    uses_values = [s["uses"] for s in steps if "uses" in s]
    assert len(uses_values) >= 2, "expected at least changed-files + github-script actions"
    for uses in uses_values:
        assert "/" in uses and "@" in uses, f"suspicious action ref: {uses!r}"
        assert not uses.endswith((".yml", ".yaml")), f"action.yml: {uses!r} looks like a workflow file, not an action"


def test_action_no_top_level_secrets():
    """action.yml must NOT declare secrets at the top level — composite actions
    have no secrets: schema of their own; whatever secrets a step needs must
    already be available in the calling job's environment."""
    action = _load_action()
    assert "secrets" not in action, (
        "action.yml: must not declare secrets at the top level"
    )


def test_action_resolver_logic_matches_resolve_paths_yml():
    """The inlined JS resolver in action.yml must stay byte-for-byte in sync
    with resolve-paths.yml's own compute step -- there are two independent
    copies (composite actions cannot `uses:` a reusable workflow to share
    the logic), so drift is a real risk this test exists to catch."""
    resolve_paths_wf = yaml.safe_load((REPO_ROOT / ".github/workflows/resolve-paths.yml").read_text())
    resolve_paths_script = None
    for step in resolve_paths_wf["jobs"]["resolve"]["steps"]:
        if step.get("id") == "compute":
            resolve_paths_script = step["with"]["script"]
            break
    assert resolve_paths_script, "resolve-paths.yml: compute step script not found"

    action_steps = _load_action()["runs"]["steps"]
    action_script = None
    for step in action_steps:
        if step.get("id") == "compute":
            action_script = step["with"]["script"]
            break
    assert action_script, "action.yml: compute step script not found"

    assert action_script.strip() == resolve_paths_script.strip(), (
        "action.yml's inlined resolver script has drifted from resolve-paths.yml's "
        "compute step -- keep them byte-identical (see this test's docstring)"
    )


# ---------------------------------------------------------------------------
# post-verdict-audit composite action
# ---------------------------------------------------------------------------


def _load_post_audit() -> dict:
    return yaml.safe_load(POST_AUDIT_FILE.read_text())


def test_post_audit_is_composite():
    assert _load_post_audit()["runs"]["using"] == "composite"


def test_post_audit_required_inputs_present():
    """The original 7 required inputs MUST stay."""
    inputs = _load_post_audit()["inputs"]
    for name in ("pr_number", "gh_token", "run_id", "job", "status", "verdict", "head_sha"):
        assert name in inputs, f"post-verdict-audit: required input {name} missing"
        assert inputs[name].get("required") is True, (
            f"post-verdict-audit.inputs.{name}: must be required"
        )


def test_post_audit_phase4_inputs_added():
    """Phase 4 adds 2 optional inputs: audit_marker + format_audit_cmd."""
    inputs = _load_post_audit()["inputs"]
    for name in ("audit_marker", "format_audit_cmd"):
        assert name in inputs, f"post-verdict-audit: Phase 4 input {name} missing"
        assert inputs[name].get("required", False) is False, (
            f"post-verdict-audit.inputs.{name}: must be optional"
        )


def test_post_audit_audit_marker_default():
    """Default audit_marker stays the dev-harness-kit default so existing
    consumers' provenance parsers keep working."""
    inputs = _load_post_audit()["inputs"]
    assert inputs["audit_marker"]["default"] == "<!-- dev-kit-verdict-audit -->"


def test_post_audit_format_audit_cmd_default_empty():
    """Default format_audit_cmd is empty → inline echo fallback for non-dev-kit consumers."""
    inputs = _load_post_audit()["inputs"]
    assert inputs["format_audit_cmd"]["default"] == ""
