"""Local mirror of the resolver script in resolve-paths.yml.

Used by `python3 -m pytest tests/` and by the CI workflow to pin
the resolver semantics against the workflow body.

Rule semantics (per docs/proposals/review/gates-distribution/00-index.yaml):

- Start from the gate default (gates.json:enabled).
- If NO rule matches: keep defaults.
- If rules match: the gate's effective value = (gate is in the UNION of
  matching rules' `gates` lists). Gates not named by any matching rule
  become False for this PR.
- mode=all: every changed path must match the rule's `when` glob set.
- mode=any: at least one changed path must match.
- Unknown gate names in a rule produce a warning; the gate is dropped.
"""
from __future__ import annotations

import re
from typing import Iterable


def match_glob(path: str, pattern: str) -> bool:
    """Inlined fnmatch-style matcher mirroring the JS implementation."""
    regex = re.escape(pattern)
    regex = regex.replace(r"\*\*", "::DOUBLESTAR::")
    regex = regex.replace(r"\*", "[^/]*")
    regex = regex.replace("::DOUBLESTAR::", ".*")
    regex = regex.replace(r"\?", ".")
    return re.fullmatch(regex, path) is not None


def rule_matches(rule: dict, paths: Iterable[str]) -> bool:
    paths = list(paths)
    matched = [p for p in paths if any(match_glob(p, g) for g in rule["when"])]
    if rule.get("mode") == "any":
        return len(matched) > 0
    return len(matched) == len(paths) and len(paths) > 0


def resolve(
    gates: dict,
    path_rules: list[dict],
    changed_paths: list[str],
) -> tuple[dict[str, bool], list[dict]]:
    """Replicate resolve-paths.yml's outputs without a workflow runner."""
    defaults = {k: bool(v["enabled"]) for k, v in gates["gates"].items()}
    warnings: list[dict] = []

    # Collect every matching rule's named-gate set.
    matched_gates: set[str] = set()
    any_match = False
    for rule in path_rules:
        if not rule_matches(rule, changed_paths):
            continue
        any_match = True
        for g in rule.get("gates", []):
            if g not in defaults:
                warnings.append({"rule": rule["name"], "gate": g, "reason": "unknown_gate_in_rule"})
                continue
            matched_gates.add(g)

    if not any_match:
        return defaults, warnings

    # Rules replaced the default set: only named gates run; un-named gates are off.
    return {k: (k in matched_gates) for k in defaults}, warnings


# ---------------------------------------------------------------------------
# Fixture cases. Lock the resolver against accidental semantic drift.
# ---------------------------------------------------------------------------

_GATES = {
    "gates": {
        "review":     {"enabled": True, "workflow": "review.yml",     "var": "GATES_REVIEW_ENABLED"},
        "security":   {"enabled": True, "workflow": "security.yml",   "var": "GATES_SECURITY_ENABLED"},
        "maintenance":{"enabled": True, "workflow": "maintenance.yml","var": "GATES_MAINTENANCE_ENABLED"},
    }
}


def test_no_rules_returns_defaults():
    out, warns = resolve(_GATES, [], ["lib/x.py"])
    assert out == {"review": True, "security": True, "maintenance": True}, out
    assert warns == []


def test_doc_only_skips_all():
    rules = [{"name": "docs", "when": ["docs/**", "README.md"], "gates": [], "mode": "all"}]
    out, warns = resolve(_GATES, rules, ["docs/x.md", "README.md"])
    assert out == {"review": False, "security": False, "maintenance": False}, out
    assert warns == []


def test_skills_runs_security_only():
    rules = [{"name": "skills", "when": ["skills/**"], "gates": ["security"], "mode": "all"}]
    out, warns = resolve(_GATES, rules, ["skills/foo.py"])
    assert out == {"review": False, "security": True, "maintenance": False}, out
    assert warns == []


def test_workflow_edit_runs_security_only():
    rules = [{"name": "wf", "when": [".github/workflows/**"], "gates": ["security"], "mode": "all"}]
    out, _ = resolve(_GATES, rules, [".github/workflows/review.yml"])
    assert out == {"review": False, "security": True, "maintenance": False}


def test_unknown_gate_warns_and_skips():
    rules = [{"name": "typo", "when": ["lib/**"], "gates": ["securty"], "mode": "all"}]
    out, warns = resolve(_GATES, rules, ["lib/x.py"])
    assert warns == [{"rule": "typo", "gate": "securty", "reason": "unknown_gate_in_rule"}]
    # The unknown gate is dropped; security is NOT named by any matching rule
    # so it ends up False. This is the correct "fail-closed" behavior — a typo
    # in a rule should NOT silently enable a gate.
    assert out == {"review": False, "security": False, "maintenance": False}, out


def test_empty_path_list_no_rule_matches():
    rules = [{"name": "any", "when": ["**"], "gates": ["security"], "mode": "all"}]
    out, _ = resolve(_GATES, rules, [])
    # mode=all with empty paths must NOT match — fall back to defaults.
    assert out == {"review": True, "security": True, "maintenance": True}


def test_mode_any_matches_with_one_path():
    rules = [{"name": "any", "when": ["lib/**"], "gates": ["security"], "mode": "any"}]
    out, _ = resolve(_GATES, rules, ["README.md", "lib/x.py"])
    assert out == {"review": False, "security": True, "maintenance": False}


def test_glob_double_star_matches_nested():
    assert match_glob("docs/foo/bar.md", "docs/**/*.md")
    assert not match_glob("docs/foo.py", "docs/**/*.md")
    assert match_glob("README.md", "*.md")
    assert match_glob("a/b/c.txt", "a/**/c.txt")


def test_multiple_matching_rules_union():
    """Two matching rules union their gate sets."""
    rules = [
        {"name": "lib", "when": ["lib/**"], "gates": ["review"], "mode": "any"},
        {"name": "workflow", "when": [".github/**"], "gates": ["security"], "mode": "any"},
    ]
    out, _ = resolve(_GATES, rules, ["lib/x.py", ".github/workflows/review.yml"])
    assert out == {"review": True, "security": True, "maintenance": False}
