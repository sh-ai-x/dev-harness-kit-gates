"""Pin the shape of the composite action (action.yml) and the post-verdict-audit
composite action (.github/actions/post-verdict-audit/action.yml).

Companion to test_workflow_call_inputs.py (which pins each reusable workflow
individually). This file pins:
  - action.yml's additive-only Phase 4 contract (no existing inputs/outputs
    removed; new ones added)
  - the post-verdict-audit composite action's inputs (including the
    Phase 4 format_audit_cmd + audit_marker additions)
"""
from __future__ import annotations

import pathlib

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ACTION_FILE = REPO_ROOT / "action.yml"
POST_AUDIT_FILE = REPO_ROOT / ".github/actions/post-verdict-audit/action.yml"


# ---------------------------------------------------------------------------
# action.yml — Phase 3 contract (must not break) + Phase 4 additions
# ---------------------------------------------------------------------------


def _load_action() -> dict:
    return yaml.safe_load(ACTION_FILE.read_text())


def test_action_is_composite():
    assert _load_action()["runs"]["using"] == "composite"


def test_action_phase3_inputs_still_present():
    """Phase 3 inputs MUST stay (additive-only contract from docs/release-process.md)."""
    inputs = _load_action()["inputs"]
    for name in ("gates_json_b64", "provider", "model", "output_artifact"):
        assert name in inputs, f"action.yml: Phase 3 input {name} was removed"


def test_action_phase3_outputs_still_present():
    outputs = _load_action()["outputs"]
    for name in ("review", "security", "maintenance", "rule_warnings"):
        assert name in outputs, f"action.yml: Phase 3 output {name} was removed"


def test_action_phase4_inputs_added():
    """Phase 4 adds new per-gate inputs defaulted to safe values."""
    inputs = _load_action()["inputs"]
    for name in (
        "plugin_repo",
        "pr_number",
        "pr_head_sha",
        "pr_title",
        "pr_is_from_fork",
        "pr_updated_at",
        "run_id",
        "docs_check_cmd",
        "format_audit_cmd",
    ):
        assert name in inputs, f"action.yml: Phase 4 input {name} missing"
        assert inputs[name]["required"] is False, (
            f"action.yml.inputs.{name}: Phase 4 inputs MUST be optional (additive only)"
        )


def test_action_phase4_outputs_added():
    """Phase 4 adds 9 new outputs: per-gate verdict / agent_ran / verdict_source."""
    outputs = _load_action()["outputs"]
    for name in (
        "review_verdict", "review_agent_ran", "review_verdict_source",
        "security_verdict", "security_agent_ran", "security_verdict_source",
        "maintenance_verdict", "maintenance_agent_ran", "maintenance_verdict_source",
    ):
        assert name in outputs, f"action.yml: Phase 4 output {name} missing"


def test_action_calls_each_judge_workflow():
    """The composite must invoke all three judges (resolve-paths + 3 gates)."""
    steps = _load_action()["runs"]["steps"]
    step_names = [s.get("name", "") for s in steps]
    assert "Resolve gate set from path_rules" in step_names
    assert "Run review gate" in step_names
    assert "Run security gate" in step_names
    assert "Run maintenance gate" in step_names
    assert len(steps) == 4, f"expected 4 composite steps, got {len(steps)}"


def test_action_gate_steps_are_conditional():
    """Each gate invocation must gate on the resolver output, not always run."""
    steps = _load_action()["runs"]["steps"]
    by_name = {s["name"]: s for s in steps}
    for name in ("Run review gate", "Run security gate", "Run maintenance gate"):
        step = by_name[name]
        assert "if" in step, f"{name}: must have an `if:` conditional on the resolver output"
        # The condition must reference the corresponding resolver output.
        resolver_out = name.split()[1].lower()  # "review" / "security" / "maintenance"
        assert f"steps.resolve.outputs.{resolver_out}" in step["if"], (
            f"{name}: if: must reference steps.resolve.outputs.{resolver_out}"
        )


def test_action_gate_steps_invoke_local_workflows():
    """The 3 gate invocations must `uses:` local workflow files (the new reusable ones)."""
    steps = _load_action()["runs"]["steps"]
    by_name = {s["name"]: s for s in steps}
    assert by_name["Run review gate"]["uses"] == "./.github/workflows/review.yml"
    assert by_name["Run security gate"]["uses"] == "./.github/workflows/security.yml"
    assert by_name["Run maintenance gate"]["uses"] == "./.github/workflows/maintenance.yml"


def test_action_no_top_level_secrets():
    """action.yml must NOT declare secrets at the top level — composite actions
    forward secrets via step-level  only."""
    action = _load_action()
    assert "secrets" not in action, (
        "action.yml: must not declare secrets at the top level (composite steps forward via step.secrets)"
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
