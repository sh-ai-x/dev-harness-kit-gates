"""Pin the workflow_call input/output contract of every reusable workflow
shipped by this repo.

This is a local pytest that mirrors the YAML pin in `.github/workflows/ci.yml`.
Both stay in sync intentionally — the YAML pin catches drift in the workflow
file, this pytest catches drift in the Python contract description.

Phase 4 added review.yml / security.yml / maintenance.yml as workflow_call
reusables (alongside the pre-existing resolve-paths.yml). All three share
the same generic provider mechanism: `provider` is an informational label
with a built-in default base_url for a couple of well-known names
(minimax, deepseek); `provider_base_url` is an explicit override that
works for ANY Anthropic-Messages-API-compatible provider (OpenAI-compatible
gateway, self-hosted proxy, a brand-new vendor) without needing a code
change to the workflow; a single `provider_api_key` secret carries
whichever key the consumer supplies for their chosen provider. This
collapsed the original N-hardcoded-branches-per-provider design (which
would have needed a new `if:` step for every new vendor) into 2 generic
branches (proxied vs. native Anthropic) shared identically across all
three judges.
"""
from __future__ import annotations

import pathlib

import pytest
import yaml


WORKFLOWS_DIR = pathlib.Path(__file__).resolve().parent.parent / ".github/workflows"

RESOLVE_PATHS_FILE = WORKFLOWS_DIR / "resolve-paths.yml"
REVIEW_FILE = WORKFLOWS_DIR / "review.yml"
SECURITY_FILE = WORKFLOWS_DIR / "security.yml"
MAINTENANCE_FILE = WORKFLOWS_DIR / "maintenance.yml"

# Inputs every Phase-4 judge workflow MUST declare. provider is optional
# (has a sensible default and works with any unrecognized label as long as
# provider_base_url is set) -- workflow_call has no enum/choice constraint,
# so "supported providers" is documentation, not schema.
SHARED_INPUTS = {
    "gates_json_b64":        {"type": "string", "required": False},
    "provider":              {"type": "string", "required": False},
    "provider_base_url":     {"type": "string", "required": False},
    "model":                 {"type": "string", "required": False},
    "plugin_repo":           {"type": "string", "required": False},
    "plugin_skill_path":     {"type": "string", "required": False},
    "install_token_secret":  {"type": "string", "required": False},
    "audit_marker":          {"type": "string", "required": False},
    "pr_number":             {"type": "string", "required": True},
    "pr_head_sha":           {"type": "string", "required": True},
    "pr_is_from_fork":       {"type": "string", "required": False},
    "pr_updated_at":         {"type": "string", "required": False},
    "run_id":                {"type": "string", "required": False},
    "severity_gate_enabled": {"type": "string", "required": False},
}

SHARED_OUTPUTS = ("verdict", "agent_ran", "verdict_source")

# Every judge takes exactly these 2 secrets: a generic provider key the
# consumer supplies themselves, and the plugin-clone token.
SHARED_SECRETS = ("install_token", "provider_api_key")

# Well-known provider labels with a built-in default provider_base_url,
# documented in each workflow's `provider` input description.
KNOWN_PROVIDER_LABELS = ("minimax", "deepseek")


def _expected_inputs_for(wf_path: pathlib.Path) -> dict:
    """Per-judge input expectation; maintenance drops pr_updated_at because
    it does not use the PR-comments retry loop."""
    expected = dict(SHARED_INPUTS)
    if wf_path.name == "maintenance.yml":
        expected.pop("pr_updated_at", None)
    return expected


# ---------------------------------------------------------------------------
# resolve-paths.yml (Phase 3 contract — unchanged)
# ---------------------------------------------------------------------------


def _load_resolve_paths() -> dict:
    return yaml.safe_load(RESOLVE_PATHS_FILE.read_text())


def test_resolve_paths_workflow_call_block_present():
    wf = _load_resolve_paths()
    assert "workflow_call" in wf[True], "expected on: workflow_call trigger"
    on = wf[True]["workflow_call"]
    assert "inputs" in on
    assert "outputs" in on


def test_resolve_paths_required_input_declared():
    on = _load_resolve_paths()[True]["workflow_call"]
    inp = on["inputs"]["gates_json_b64"]
    assert inp["type"] == "string"
    assert inp["required"] is True
    assert "description" in inp


def test_resolve_paths_outputs_include_gate_booleans():
    outs = _load_resolve_paths()[True]["workflow_call"]["outputs"]
    for key in ("review", "security", "maintenance", "rule_warnings"):
        assert key in outs, f"missing output: {key}"
        assert "description" in outs[key]
        assert "value" in outs[key]


def test_resolve_paths_no_secrets_declared():
    """A reusable workflow in this repo must NEVER declare `secrets:`."""
    text = RESOLVE_PATHS_FILE.read_text()
    assert "secrets:" not in text, "resolve-paths.yml must not declare secrets"


# ---------------------------------------------------------------------------
# Phase 4 judge workflows (review / security / maintenance)
# ---------------------------------------------------------------------------


def _load_judge(path: pathlib.Path) -> dict:
    wf = yaml.safe_load(path.read_text())
    assert "workflow_call" in wf[True], f"{path.name}: expected on: workflow_call"
    return wf[True]["workflow_call"]


@pytest.mark.parametrize("wf_path,default_skill", [
    (REVIEW_FILE, "skills/review/SKILL.md"),
    (SECURITY_FILE, "skills/security/SKILL.md"),
    (MAINTENANCE_FILE, "skills/maintenance/SKILL.md"),
])
def test_judge_workflow_is_workflow_call(wf_path, default_skill):
    wf = _load_judge(wf_path)
    assert "inputs" in wf
    assert "outputs" in wf
    assert "secrets" in wf, f"{wf_path.name}: must declare secrets"


@pytest.mark.parametrize("wf_path,default_skill", [
    (REVIEW_FILE, "skills/review/SKILL.md"),
    (SECURITY_FILE, "skills/security/SKILL.md"),
    (MAINTENANCE_FILE, "skills/maintenance/SKILL.md"),
])
def test_judge_workflow_shared_inputs_present(wf_path, default_skill):
    inputs = _load_judge(wf_path)["inputs"]
    for name, expected in _expected_inputs_for(wf_path).items():
        assert name in inputs, f"{wf_path.name}: missing shared input {name}"
        for key, val in expected.items():
            if isinstance(val, bool):
                assert inputs[name][key] is val, (
                    f"{wf_path.name}.inputs.{name}.{key}: expected {val}, got {inputs[name][key]}"
                )
            else:
                assert inputs[name][key] == val, (
                    f"{wf_path.name}.inputs.{name}.{key}: expected {val}, got {inputs[name][key]}"
                )


@pytest.mark.parametrize("wf_path,default_skill", [
    (REVIEW_FILE, "skills/review/SKILL.md"),
    (SECURITY_FILE, "skills/security/SKILL.md"),
    (MAINTENANCE_FILE, "skills/maintenance/SKILL.md"),
])
def test_judge_workflow_shared_outputs_present(wf_path, default_skill):
    outputs = _load_judge(wf_path)["outputs"]
    for key in SHARED_OUTPUTS:
        assert key in outputs, f"{wf_path.name}: missing shared output {key}"
        assert "value" in outputs[key]


@pytest.mark.parametrize("wf_path,default_skill", [
    (REVIEW_FILE, "skills/review/SKILL.md"),
    (SECURITY_FILE, "skills/security/SKILL.md"),
    (MAINTENANCE_FILE, "skills/maintenance/SKILL.md"),
])
def test_judge_workflow_plugin_skill_path_default(wf_path, default_skill):
    """Each judge's plugin_skill_path default MUST point at the matching skill."""
    inputs = _load_judge(wf_path)["inputs"]
    assert inputs["plugin_skill_path"]["default"] == default_skill, (
        f"{wf_path.name}: plugin_skill_path default should be {default_skill}"
    )


@pytest.mark.parametrize("wf_path", [REVIEW_FILE, SECURITY_FILE, MAINTENANCE_FILE])
def test_judge_workflow_secrets_declared(wf_path):
    """Every judge must declare exactly the 2 shared secrets: install_token
    (plugin clone) and provider_api_key (the consumer's own key, never a
    dev-kit-provided default)."""
    secrets = _load_judge(wf_path)["secrets"]
    for name in SHARED_SECRETS:
        assert name in secrets, f"{wf_path.name}: must declare secrets.{name}"


@pytest.mark.parametrize("wf_path", [REVIEW_FILE, SECURITY_FILE, MAINTENANCE_FILE])
def test_judge_workflow_no_provider_specific_secret_names(wf_path):
    """No judge may declare a per-provider secret name (MINIMAX_API_KEY,
    ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, etc.) -- the whole point of the
    generic provider_base_url + provider_api_key design is that adding a
    new provider requires zero code changes to this workflow, including
    zero new secret declarations."""
    secrets = _load_judge(wf_path)["secrets"]
    forbidden = {"MINIMAX_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"}
    leaked = forbidden & set(secrets.keys())
    assert not leaked, f"{wf_path.name}: provider-specific secret names found: {leaked}"


def test_maintenance_extra_inputs():
    """Maintenance has 4 extra inputs (bump_pr_skip_pattern, docs_check_cmd,
    format_audit_cmd, pr_title). Review and security don't."""
    inputs = _load_judge(MAINTENANCE_FILE)["inputs"]
    for name in ("bump_pr_skip_pattern", "docs_check_cmd", "format_audit_cmd", "pr_title"):
        assert name in inputs, f"maintenance.yml: missing extra input {name}"


@pytest.mark.parametrize("wf_path", [REVIEW_FILE, SECURITY_FILE, MAINTENANCE_FILE])
def test_provider_description_documents_known_labels(wf_path):
    """All 3 judges support the SAME generic provider mechanism -- every
    known-label default (minimax, deepseek) must be documented identically
    across all three, since none of them hardcode which labels are
    'allowed' anymore."""
    desc = _load_judge(wf_path)["inputs"]["provider"]["description"]
    for label in KNOWN_PROVIDER_LABELS:
        assert label in desc, f"{wf_path.name}: provider description must mention {label}"


@pytest.mark.parametrize("wf_path", [REVIEW_FILE, SECURITY_FILE, MAINTENANCE_FILE])
def test_provider_base_url_empty_default(wf_path):
    """provider_base_url defaults to empty (native Anthropic unless a
    known provider label or an explicit override resolves one)."""
    inputs = _load_judge(wf_path)["inputs"]
    assert inputs["provider_base_url"]["default"] == "", (
        f"{wf_path.name}: provider_base_url must default to empty string"
    )


@pytest.mark.parametrize("wf_path", [REVIEW_FILE, SECURITY_FILE, MAINTENANCE_FILE])
def test_judge_step_names_are_provider_agnostic(wf_path):
    """The 2 judge-invocation steps must be named generically ('proxied
    provider' / 'native anthropic'), not after a specific vendor -- this
    is the direct evidence that adding a new provider needs no new step."""
    wf = yaml.safe_load(wf_path.read_text())
    job_name = "maintenance_judge" if wf_path.name == "maintenance.yml" else wf_path.stem
    steps = wf["jobs"][job_name]["steps"]
    step_names = {s.get("name", "") for s in steps}
    assert any("proxied provider" in n for n in step_names), (
        f"{wf_path.name}: missing a generic 'proxied provider' step"
    )
    assert any("native anthropic" in n for n in step_names), (
        f"{wf_path.name}: missing a generic 'native anthropic' step"
    )
    forbidden_vendor_names = {"minimax", "deepseek", "codex"}
    for n in step_names:
        lowered = n.lower()
        for vendor in forbidden_vendor_names:
            assert vendor not in lowered, (
                f"{wf_path.name}: step {n!r} names a specific vendor -- "
                "the generic design should have no per-vendor step names"
            )


def test_judge_workflow_no_pull_request_trigger():
    """Each judge workflow declares `on: workflow_call` (not pull_request),
    confirming they are reusable — not consumer wrappers."""
    for wf_path in (REVIEW_FILE, SECURITY_FILE, MAINTENANCE_FILE):
        wf = yaml.safe_load(wf_path.read_text())
        on = wf[True]
        assert "workflow_call" in on, f"{wf_path.name}: missing workflow_call trigger"
        assert "pull_request" not in on, (
            f"{wf_path.name}: must NOT declare on: pull_request (it's a reusable)"
        )


def test_severity_gate_enabled_default_true():
    """severity_gate_enabled defaults to 'true' on every judge workflow."""
    for wf_path in (REVIEW_FILE, SECURITY_FILE, MAINTENANCE_FILE):
        inputs = _load_judge(wf_path)["inputs"]
        assert inputs["severity_gate_enabled"]["default"] == "true", (
            f"{wf_path.name}: severity_gate_enabled must default to 'true'"
        )


def test_downstream_gate_job_respects_severity_gate_enabled():
    """The downstream deterministic gate job (severity_gate / gate) must be
    skippable via inputs.severity_gate_enabled, while the upstream judge
    agent job (review / security / maintenance_judge) always runs
    regardless -- this mirrors the dev-harness-kit source behavior where
    GATES_<NAME>_ENABLED=false only disables the CI hard-fail, not the
    AI review itself."""
    downstream_job_name = {
        REVIEW_FILE: "severity_gate",
        SECURITY_FILE: "severity_gate",
        MAINTENANCE_FILE: "gate",
    }
    for wf_path, job_name in downstream_job_name.items():
        wf = yaml.safe_load(wf_path.read_text())
        job = wf["jobs"][job_name]
        assert "if" in job, f"{wf_path.name}.jobs.{job_name}: missing if: condition"
        assert "severity_gate_enabled" in job["if"], (
            f"{wf_path.name}.jobs.{job_name}.if: must reference inputs.severity_gate_enabled"
        )
