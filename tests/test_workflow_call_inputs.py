"""Pin the workflow_call input/output contract of resolve-paths.yml.

This is a local pytest that mirrors the YAML pin in `.github/workflows/ci.yml`.
Both stay in sync intentionally — the YAML pin catches drift in the workflow
file, this pytest catches drift in the Python contract description.
"""
from __future__ import annotations

import pathlib

import yaml


WF_PATH = pathlib.Path(__file__).resolve().parent.parent / ".github/workflows/resolve-paths.yml"


def _load() -> dict:
    return yaml.safe_load(WF_PATH.read_text())


def test_workflow_call_block_present():
    wf = _load()
    assert "workflow_call" in wf[True], "expected on: workflow_call trigger"
    on = wf[True]["workflow_call"]
    assert "inputs" in on
    assert "outputs" in on


def test_required_input_declared():
    on = _load()[True]["workflow_call"]
    inp = on["inputs"]["gates_json_b64"]
    assert inp["type"] == "string"
    assert inp["required"] is True
    assert "description" in inp


def test_outputs_include_gate_booleans():
    outs = _load()[True]["workflow_call"]["outputs"]
    for key in ("review", "security", "maintenance", "rule_warnings"):
        assert key in outs, f"missing output: {key}"
        assert "description" in outs[key]
        assert "value" in outs[key]


def test_no_secrets_declared_in_workflow():
    """A reusable workflow in this repo must NEVER declare `secrets:`.

    All secrets are passed through by the consumer wrapper, never owned by
    this repo. A regression that adds `secrets:` would silently couple the
    marketplace action to consumer credentials — exactly the failure mode
    the SSOT-link design avoids.
    """
    text = WF_PATH.read_text()
    assert "secrets:" not in text, "resolve-paths.yml must not declare secrets"
