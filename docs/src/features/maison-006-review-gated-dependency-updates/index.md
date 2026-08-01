# MAISON-006: Review-gated dependency updates

## Delivery Summary

- Beads feature root: `maison-mol-aqu`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison's cache-refresh automation no longer approves or merges dependency updates. The workflow may refresh `flake.lock`, build the proposed cache targets, warm Cachix, and open or update the `automation/refresh-flake-lock` pull request. It leaves dependency acceptance to ordinary pull request review and branch protection.

The repository now has source guards that reject reintroducing dependency automation that invokes `gh pr merge`, passes `--admin`, enables auto-merge, or recreates the removed merge approval job.

## User-Facing Behavior

Operators and contributors still use the existing update surfaces. Manual `maison update` behavior is unchanged. Scheduled cache refresh can prepare a reviewed flake-lock PR with warmed cache artifacts, but the PR remains open until a human review and protected-branch merge accepts it.

## Design Integration

The implementation keeps Nix input semantics unchanged: `flake.lock` remains the pinned Nix dependency source and update PRs remain normal repository changes. It narrows only the CI delivery path by removing the administrative merge stage from `.github/workflows/cache-refresh.yml`.

No new approval service, command surface, or repository ownership layer was introduced. GitHub pull request review and branch protection are the dependency approval mechanism.

## Operational Impact

Maintainers should expect cache refresh runs with dependency changes to produce or update an automation PR rather than merge it. The reusable hk and CI workflow runs still execute against `automation/refresh-flake-lock` when a PR is present, so reviewers can use the warmed cache and validation evidence before deciding whether to merge.

## Reference and Contracts

- [Operations](../../operations.md)
- [Developer tooling](../../development/tooling.md)
- [Tooling reference](../../reference/tooling.md)

## Validation Evidence

- `python3 -m py_compile tests/test_topology.py` — passed.
- `python3 -m unittest -v tests.test_topology.ReviewGatedDependencyUpdateTest` — passed.
- `uv run scripts/check-docs.py` — passed.
- `mise -E dev exec -- actionlint .github/workflows/cache-refresh.yml` — passed.
- `mise -E dev run check` — passed.

## Design Reconciliation

### Delivered as Designed

- Removed the automated `merge-lock-pr` job from `.github/workflows/cache-refresh.yml`.
- Preserved cache warming and update PR creation/update behavior.
- Added tests that fail if dependency automation uses `gh pr merge`, `--admin`, auto-merge, or an approval merge job.
- Updated reader-facing operations, development tooling, and tooling reference docs.

### Intentional Changes

- Documentation paths were corrected during specification review from non-existent root-level development/reference pages to the current `docs/src/development/tooling.md` and `docs/src/reference/tooling.md` pages.

### Deferred Work

None.

### Rejected or Removed Scope

- Administrative PR merge bypass was removed from cache refresh automation.
- A new approval service or Maison command was not introduced.

## Documentation Updated

- `docs/operations.md`
- `docs/src/development/tooling.md`
- `docs/src/reference/tooling.md`
- `docs/src/features/maison-006-review-gated-dependency-updates/design.md`
- `docs/src/features/maison-006-review-gated-dependency-updates/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation task: `maison-mol-642`, commit `0f4e563`.
- Implementation coordinator: `maison-mol-73y`.
- CI contract task: `maison-mol-73y.1`, commit `b45e97f`.
- CI implementation task: `maison-mol-73y.2`, commit `f3682a1`.
- Documentation reconciliation task: `maison-mol-4jj`.
- Validation task: `maison-mol-aqw`.
