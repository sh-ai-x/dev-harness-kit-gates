# dev-harness-kit/gates

GitHub Actions reusable workflows and a composite action for the
[dev-harness-kit](https://github.com/sh-ai-x/dev-harness-kit) gate
machinery: `review`, `security`, `maintenance`, and the per-path rule
resolver. (`auto-fix-pr` is deferred to Phase 5 — see Roadmap.)

## What this repo is

The dev-harness-kit plugin owns the source-of-truth state files
(`.dev-kit/gates.json`, `.dev-kit/ci-config.json`) and the operator UX
(`/dev-kit:gate-select`, `/dev-kit:ci-setup`). This repository owns
the **executable** gate payloads — the reusable workflows that the
plugin's `ci-setup` skill points at.

Splitting the workflow payload from the plugin means a security fix
to the review judge ships as `dev-harness-kit/gates@v1.4.3` without
waiting for a dev-harness-kit plugin release.

## What's in here

```text
dev-harness-kit/gates
├── action.yml                                    # composite action: resolve + 3 gate invocations
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                                # test runner for this repo itself
│   │   ├── resolve-paths.yml                     # workflow_call: Half B resolver (Phase 3)
│   │   ├── review.yml                            # workflow_call: review judge (Phase 4)
│   │   ├── security.yml                          # workflow_call: security judge (Phase 4)
│   │   └── maintenance.yml                       # workflow_call: maintenance judge (Phase 4)
│   └── actions/
│       └── post-verdict-audit/action.yml         # composite action: post the audit comment
├── scripts/
│   ├── extract_verdict.py                        # universal: parse agent execution file
│   ├── verdict_from_comment.py                   # universal: parse PR-comment fallback
│   ├── verdict_comments_fallback.sh              # universal: retry-loop wrapper
│   └── extract_verdict_from_text.py              # universal: bold-form lenient extractor
├── tests/
│   ├── test_workflow_call_inputs.py              # per-workflow input/output pin
│   ├── test_universal_helpers.py                 # parser behavior pin
│   ├── test_judge_workflow_shape.py              # action.yml + post-verdict-audit shape pin
│   ├── test_resolve_paths_logic.py               # JS-glob-matcher Python mirror
│   └── test_wrapper_budget.py                    # workflow line cap + file allow-list
└── docs/
    ├── marketplace-checklist.md                  # GitHub Marketplace publishing requirements
    └── release-process.md                        # version tag policy + backward-compat contract
```

## Versioning

| Tag | Status | Use |
|---|---|---|
| `@v0` | private / pre-release | first publish; consumers should NOT pin yet |
| `@v1` | public marketplace | first stable major; consumers pin `@v1` for forward-compatible minor bumps |
| `@v1.x.x` | patch | bug fixes, security patches; no input shape changes |
| `@v2` | breaking | required for any input/output removal or rename |

`v1.x` may add inputs/outputs; it may not change the meaning of
existing ones or remove them. A breaking change requires a new
major version and a one-major-version deprecation window documented
in `docs/release-process.md`.

## SSOT link

Consumer repos carry `.dev-kit/gates.json` as the gate SSOT. This
repository never reads `.dev-kit/gates.json` directly — the consumer
wrappers base64-encode the `path_rules` block and pass it as
`with: gates_json_b64`. This keeps the marketplace action free of
consumer secrets and avoids implicit file-system assumptions.

## Per-judge input contract (Phase 4)

Every Phase 4 judge workflow (`review.yml` / `security.yml` /
`maintenance.yml`) shares the same `workflow_call` input contract:

| Input | Type | Required | Default | Description |
|---|---|---|---|---|
| `gates_json_b64` | string | yes | — | base64-encoded JSON of `.dev-kit/gates.json` minus secrets |
| `provider` | choice | yes | `minimax` | one of `minimax`, `claude`, `codex` (and `deepseek` for maintenance) |
| `model` | string | no | `""` | provider model override; empty = provider default |
| `plugin_repo` | string | no | `sh-ai-x/dev-harness-kit` | GitHub slug of the plugin source |
| `plugin_skill_path` | string | no | `skills/<gate>/SKILL.md` | path to the skill file inside the plugin |
| `install_token_secret` | string | no | `DEV_KIT_GITHUB_TOKEN` | name of the secret holding the install token (informational) |
| `audit_marker` | string | no | `<!-- dev-kit-verdict-audit -->` | HTML marker used in audit comments |
| `bump_pr_skip_pattern` | string | no (maintenance only) | `chore(release): bump dev-kit to v` | PR title prefix to skip |
| `docs_check_cmd` | string | no (maintenance only) | `""` | shell command for the docs-updated sub-gate |
| `format_audit_cmd` | string | no (maintenance only) | `""` | shell command for the audit body format |
| `pr_number` | string | yes | — | PR number the judge is reviewing |
| `pr_head_sha` | string | yes | — | PR head commit SHA (closes the agent→checkout TOCTOU) |
| `pr_title` | string | no (maintenance only) | `""` | PR title (used for bump-PR skip) |
| `pr_is_from_fork` | string | no | `false` | true → skip the agent run |
| `pr_updated_at` | string | no | `""` | PR updated_at ISO timestamp (used as fallback cutoff for the PR-comments retry loop on review/security) |
| `run_id` | string | no | `0` | GitHub Actions run id (used for the audit comment) |

The 3 shared outputs are `verdict`, `agent_ran`, and `verdict_source`.

## Consumer examples

### Review gate (replaces `templates/ci/.github/workflows/review.yml`)

```yaml
name: review
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
  workflow_dispatch:
    inputs:
      review_provider: { type: choice, options: ["", minimax, anthropic], default: "" }
      pr_number:       { type: string }
concurrency:
  group: review-pr-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
permissions:
  contents: read
  pull-requests: write
jobs:
  review:
    if: |
      github.event_name == 'workflow_dispatch' ||
      github.event.pull_request.head.repo.full_name == github.repository
    uses: sh-ai-x/dev-harness-kit-gates/.github/workflows/review.yml@v1
    with:
      gates_json_b64: ${{ vars.GATES_PATH_RULES_B64 }}
      provider: ${{ inputs.review_provider || vars.CI_REVIEW_PROVIDER || 'minimax' }}
      pr_number: ${{ github.event.pull_request.number || inputs.pr_number }}
      pr_head_sha: ${{ github.event.pull_request.head.sha || github.sha }}
      pr_is_from_fork: ${{ github.event.pull_request.head.repo.full_name != github.repository }}
      pr_updated_at: ${{ github.event.pull_request.updated_at }}
      run_id: ${{ github.run_id }}
    secrets:
      install_token: ${{ secrets.DEV_KIT_GITHUB_TOKEN }}
```

(security.yml + maintenance.yml follow the same shape; maintenance
adds `bump_pr_skip_pattern`, `docs_check_cmd`, `format_audit_cmd`,
`pr_title`.)

### Composite action (one-shot invocation)

```yaml
jobs:
  gates:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      id-token: write
    steps:
      - uses: sh-ai-x/dev-harness-kit-gates@v1
        id: gates
        with:
          gates_json_b64: ${{ vars.GATES_PATH_RULES_B64 }}
          provider: ${{ vars.CI_REVIEW_PROVIDER || 'minimax' }}
          pr_number: ${{ github.event.pull_request.number }}
          pr_head_sha: ${{ github.event.pull_request.head.sha }}
          pr_is_from_fork: ${{ github.event.pull_request.head.repo.full_name != github.repository }}
          docs_check_cmd: "python3 -m lib.maintenance_gate"
        env:
          MINIMAX_API_KEY: ${{ secrets.MINIMAX_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Roadmap

See the parent proposal:
[`docs/proposals/review/gates-distribution/00-index.yaml`](https://github.com/sh-ai-x/dev-harness-kit/blob/main/docs/proposals/review/gates-distribution/00-index.yaml)

| Phase | Status | Contents |
|---|---|---|
| Phase 3 | done | scaffolding: README + `action.yml` + `resolve-paths.yml` + tests + CI |
| Phase 4 | done | migrate review.yml / security.yml / maintenance.yml (+ universal helpers) from `templates/ci/.github/workflows/` to this repo |
| Phase 5 | pending | migrate `auto-fix-pr.yml` (SPECIFIC to dev-harness-kit; deferred); marketplace publish (icon, listing, README polish) |

## Known limitations

- **`auto-fix-pr.yml` deferred.** Auto-fix couples to `lib/repair_coordinator.py`
  and the `auto-fix/iter-N` label protocol — both dev-harness-kit-specific.
  Phase 4 ships 3 of 4 judges; auto-fix lands in Phase 5 with the
  consumer passing the SPECIFIC bits through `with:`.
- **`codex` provider** has no source branch in the migrated workflows
  — they fall through to the `anthropic` env block (codex reuses the
  Anthropic env-var convention). Fork the workflow if you need a
  codex-specific env.
- **Provider env-var mismatch.** Source workflows hardcode
  `MINIMAX_BASE_URL=https://api.minimax.io/anthropic`. Defaults to
  `minimax` for backward compat; consumers on `claude` / `codex` /
  `deepseek` pass through provider-specific envs as today.
- **Audit marker ownership.** `<!-- dev-kit-verdict-audit -->` is
  consumed by parent's `lib/maintenance_gate.py` for provenance.
  Default stays the marker; `audit_marker` input offered for
  non-dev-kit consumers.

## License

MIT — see [LICENSE](./LICENSE).
