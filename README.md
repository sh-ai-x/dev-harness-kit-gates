# dev-harness-kit/gates

GitHub Actions reusable workflows and a composite action for the
[dev-harness-kit](https://github.com/sh-ai-x/dev-harness-kit) gate
machinery: `review`, `security`, `maintenance`, `auto-fix-pr`, and the
per-path rule resolver.

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
├── action.yml                       # composite action, single-line uses entry
├── .github/workflows/
│   ├── ci.yml                       # test runner for this repo itself
│   ├── resolve-paths.yml            # workflow_call: Half B resolver
│   ├── review.yml                   # workflow_call (migrated Phase 4)
│   ├── security.yml                 # workflow_call (migrated Phase 4)
│   ├── maintenance.yml              # workflow_call (migrated Phase 4)
│   └── auto-fix-pr.yml              # workflow_call (migrated Phase 4)
├── tests/                           # workflow_call input pin + resolver fixture tests
│   ├── test_workflow_call_inputs.py
│   ├── test_resolve_paths_action.py
│   └── test_wrapper_budget.py
└── docs/
    ├── marketplace-checklist.md     # GitHub Marketplace publishing requirements
    └── release-process.md           # version tag policy + backward-compat contract
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

```yaml
# consumer .github/workflows/review.yml
name: review
on:
  pull_request:
    branches: [main]
permissions:
  contents: read
  pull-requests: write
jobs:
  review:
    uses: dev-harness-kit/gates/.github/workflows/review.yml@v1
    with:
      gates_json_b64: ${{ vars.GATES_PATH_RULES_B64 }}
      provider: ${{ vars.CI_REVIEW_PROVIDER }}
    secrets:
      DEV_KIT_GITHUB_TOKEN: ${{ secrets.DEV_KIT_GITHUB_TOKEN }}
      anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
      minimax_api_key: ${{ secrets.MINIMAX_API_KEY }}
```

## Inputs (shared contract)

| Input | Type | Required | Description |
|---|---|---|---|
| `gates_json_b64` | string | yes | base64-encoded JSON of `.dev-kit/gates.json` minus secrets |
| `provider` | string | yes | one of `minimax`, `claude`, `codex`; matches `CI_REVIEW_PROVIDER` |
| `model` | string | no | override provider default; consumer-controlled |
| `changed_paths` | string[] | yes | paths touched by the PR (passed via resolve-paths upstream) |
| `output_artifact` | string | no | name of the artifact storing the verdict comment payload |

Secrets are passed through, never declared in this repo.

## Roadmap

See the parent proposal:
[`docs/proposals/review/gates-distribution/00-index.yaml`](https://github.com/sh-ai-x/dev-harness-kit/blob/main/docs/proposals/review/gates-distribution/00-index.yaml)

| Phase | Status | Contents |
|---|---|---|
| Phase 3 (current) | scaffolding | this README + `action.yml` + `resolve-paths.yml` + tests + CI |
| Phase 4 | judge migration | move review.yml / security.yml / maintenance.yml / auto-fix-pr.yml from `templates/ci/.github/workflows/` to this repo as reusable workflows |
| Phase 5 | marketplace publish | open public listing, add icon, README polish |

## License

MIT — see [LICENSE](./LICENSE).
