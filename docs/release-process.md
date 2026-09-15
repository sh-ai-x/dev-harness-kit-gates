# Release process

## Versioning policy

`dev-harness-kit/gates` follows the GitHub Actions tag convention
(`vMAJOR.MINOR.PATCH`).

### `v1.x.x` (current major)

Permitted:
- Add new inputs/outputs
- Add new reusable workflows under `.github/workflows/`
- Bug fixes that do not change existing input/output semantics
- Security patches
- Documentation improvements

Forbidden:
- Remove or rename an input/output
- Change the meaning of an existing input
- Change the default branch for the resolved gate set
- Drop support for an already-declared `provider`

A forbidden change MUST bump `v2` and follow the deprecation window
below. Bug fixes that go through "exotic" code paths (e.g., a different
resolver strategy) MUST keep producing identical outputs for every
fixture in `tests/`.

### `v2` (breaking) — deprecation window

Before tagging `v2.0.0`:

1. Announce the breaking change in the dev-harness-kit release notes
   for at least one minor cycle.
2. Tag a `v1.x` release with the deprecated path still working, and
   emit a `::warning::` step summary on every run that uses it.
3. Update `README.md` and the marketplace listing to call out the
   migration path.
4. Tag `v2.0.0` only after at least one minor cycle has passed since
   the warning was first emitted.

## Tag policy

| Tag | When |
|---|---|
| `v0.x.x` | pre-Phase-4; consumers should not pin yet |
| `v1.0.0` | first public major; pinned by consumers |
| `v1.x.x` | additive changes, bug fixes, security patches |
| `v2.0.0` | breaking change after deprecation window |

## Hotfix procedure

1. Branch from the latest `v1.x` tag (not `main`) for hotfixes.
2. Land the patch on `main` with a backport PR.
3. Tag `v1.<next>.x` and update the marketplace release notes.

The hotfix branch is deleted after the backport merges; it is not
kept around for traceability.
