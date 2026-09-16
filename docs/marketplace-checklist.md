# Marketplace publishing checklist

This is the operations checklist for opening the gates repo for public use.
Each row links the requirement to the file it lives in.

| # | Step | Owner | File | Exit condition |
|---|---|---|---|---|
| 1 | `action.yml` validates as a composite action | maintainer | `action.yml` | `actionlint` clean |
| 2 | Icon (SVG/PNG, 64x64+) uploaded | ops | repo settings → Social Preview | visible on the marketplace listing |
| 3 | One-line description + topics | ops | repo settings → About | appears in marketplace search |
| 4 | `README.md` has usage example, inputs/outputs table, license | maintainer | `README.md` | renders on listing |
| 5 | Tag `v0` released | ops | Releases → `v0.0.1` | `gh release create v0.0.1` succeeds |
| 6 | Workflow security baseline (`zizmor` clean, pinned actions, no `pull_request_target`) | maintainer | `.github/workflows/*.yml` | `zizmor .` returns 0 |
| 7 | Wrapper budget test green | maintainer | `tests/test_wrapper_budget.py` | `python3 -m pytest tests/test_wrapper_budget.py -v` returns 0 (now runnable: Phase 4 promoted the test from stub to a real cap check) |
| 8 | Backward-compat contract published | maintainer | `docs/release-process.md` | one-page doc with input/output stability rules |
| 9 | Promote `@v0` → `@v1` | both | Releases → `v1.0.0` | marketplace listing updated |
| 10 | Public listing opened | ops | marketplace publisher flow | URL published in dev-harness-kit README |

## Why order matters

The wrapper budget test (step 7) cannot run until Phase 4 lands the
migrated consumer wrappers in dev-harness-kit. Until then, `@v0` is
private and only dev-harness-kit's own fixtures pin it. Promoting to
`@v1` (step 9) is the public commitment; do it only after step 7 is
green twice (once on the dev-harness-kit fixture, once on a second
external consumer if available).

## Rollback

| Failure | Action |
|---|---|
| `zizmor` finds a real issue | patch the workflow, retag `@v0.x+1`, do not promote |
| Wrapper budget regression after `@v1` | retag the last good commit as `@v1.x`, unpublish listing, file a Phase 4 follow-up |
| A consumer hits a breaking input shape on `@v1` | that violates the contract in `docs/release-process.md`; ship a patch under the same major and call out the deviation in the next dev-harness-kit release notes |
