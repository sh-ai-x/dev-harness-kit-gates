# Changelog

All notable changes to `dev-harness-kit/gates` are documented here.
This repo follows [semver](https://semver.org/) per `docs/release-process.md`.

## [0.4.0] — Phase 4 — Judge migration (2026-09-16)

### Added

- `.github/workflows/review.yml` — `workflow_call` reusable for the review judge.
  Universal: bootstrap-PR fallback detection, verdict extraction, severity gate,
  audit comment format. dev-harness-kit-specific install paths parameterized via
  `inputs.plugin_repo` / `inputs.plugin_skill_path` / `secrets.install_token`.
- `.github/workflows/security.yml` — `workflow_call` reusable for the security judge.
  Mirrors the review.yml shape; defaults to `skills/security/SKILL.md`.
- `.github/workflows/maintenance.yml` — `workflow_call` reusable for the
  maintenance judge. Adds four maintenance-only inputs:
  `bump_pr_skip_pattern`, `docs_check_cmd`, `format_audit_cmd`, `pr_title`.
  Provider enum extended to include `deepseek`.
- `.github/actions/post-verdict-audit/action.yml` — composite action re-authored
  with two new inputs: `audit_marker` (default `<!-- dev-kit-verdict-audit -->`)
  and `format_audit_cmd` (default empty → inline echo fallback). Existing
  dev-harness-kit consumers keep working by passing
  `format_audit_cmd: "python3 -m lib.maintenance_gate --format-audit"`.
- `scripts/extract_verdict.py` — verbatim copy of
  `templates/ci/scripts/extract-verdict.py`. Renamed for path consistency.
- `scripts/verdict_from_comment.py` — verbatim copy of
  `templates/ci/.github/workflows/_verdict_from_comment.py`.
- `scripts/verdict_comments_fallback.sh` — verbatim copy of
  `templates/ci/.github/workflows/_verdict_comments_fallback.sh`. Path edit:
  helper reference updated from `.github/workflows/_verdict_from_comment.py`
  to `scripts/verdict_from_comment.py`.
- `scripts/extract_verdict_from_text.py` — new lenient extractor (tolerates both
  plain-form `Verdict:` and Markdown-bold `**Verdict:**`). Used by maintenance's
  inline jq-then-python fallback chain.
- `tests/test_universal_helpers.py` — pins the parser behavior of the four
  scripts: empty / HTML / parseable / no-verdict / last-wins / MINIMAX envelope /
  error-skip / non-candidate-skip / comments-fallback / bold-form / cutoff filter.
- `tests/test_judge_workflow_shape.py` — pins the action.yml + post-verdict-audit
  composite-action shapes (additive-only contract; per-gate inputs + outputs).
- `tests/test_workflow_call_inputs.py` — extended with per-judge parametrized
  pins; the Phase 3 resolve-paths.yml pins are preserved.
- `tests/test_wrapper_budget.py` — promoted from stub to real check: line cap
  (800 per workflow), allowed-file set, action.yml references every reusable.
- `.github/workflows/ci.yml` — added `judge-workflow-call-shape` job that runs
  on every PR to enforce the new workflow_call shape.
- `action.yml` — extended additively with 9 new inputs (all optional) and 9 new
  outputs (per-gate verdict / agent_ran / verdict_source). Existing 4 inputs and
  4 outputs are unchanged. The composite now invokes review.yml / security.yml /
  maintenance.yml conditionally on the resolver outputs.

### Changed

- `README.md` — updated Roadmap table (Phase 4 → done; Phase 5 → auto-fix +
  marketplace publish). Added per-judge input contract table + consumer examples.
- `docs/marketplace-checklist.md` — step 7 (wrapper budget) marked runnable.

### Deferred to Phase 5

- `auto-fix-pr.yml` migration — SPECIFIC to dev-harness-kit (couples to
  `lib/repair_coordinator.py` deep import, `.dev-kit/repair/events.jsonl`,
  `auto-fix/iter-N` label protocol). Phase 5 will parameterize the bounded-repair
  shell and let the consumer pass the SPECIFIC bits through `with:`.
- Marketplace publish (icon, public listing, marketplace metadata).

## [0.3.350] — 2026-09-15 — Slot-freshness guard

- No-op `.claude-plugin/plugin.json` + `.codex-plugin/plugin.json` added to satisfy
  `git-guard.sh`'s slot-freshness check in the parent dev-harness-kit repo.
  Corrected author identity (sh-ai-x <tkd1496@gmail.com>).

## [0.1.0] — Phase 3 — Scaffolding

- Initial scaffold: `action.yml` (composite action), `.github/workflows/resolve-paths.yml`
  (per-path rule resolver), `.github/workflows/ci.yml` (this repo's CI), three
  pytest files, two docs (`marketplace-checklist.md`, `release-process.md`),
  this README, and an MIT LICENSE.
