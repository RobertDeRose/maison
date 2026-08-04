# MAISON-012: Plan/apply semantic parity

## Delivery Summary

- Beads feature root: `maison-mol-6w9`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison now builds user convergence from one structured Python command plan. `maison user plan` and `maison user apply`
use the same force-dotfile semantics and ordered convergence steps; plan renders the supported dry-run commands without
executing convergence or trust operations.

## User-Facing Behavior

Dotfile replacement is opt-in for both preview and apply. By default, `maison user plan` and `maison user apply` do not
force replacement of whole-file conflicts. To preview and then apply the same forced handoff, run:

```bash
maison user plan --force-dotfiles
maison user apply --force-dotfiles
```

`maison plan --force-dotfiles` forwards that user-layer flag after its system preview, matching aggregate apply.

## Design Integration

`.mise/lib/user_convergence.py` owns the ordered user convergence plan: preparation, dotfiles, mise lock links,
packages, remaining mise user state, plus apply-only repository trust and finalization. The shell tasks remain thin
argument adapters. Plan renders dry-run variants for preparation, dotfiles, lock links, packages, and remaining mise user
state without invoking them; apply uses the existing package helper, repository trust, and finalization. These
execution-only substitutions preserve the Nix/Lix system and mise user ownership boundary.

## Operational Impact

Use the same `--force-dotfiles` choice for preview and apply. A forced preview renders the intended command sequence
without modifying files. A forced apply backs up the exact targets before replacement. Existing package-manager dry-run
capabilities are unchanged. The plan renderer no longer invokes those commands, so planning cannot alter mise trust state, dotfiles, lock
links, migration backups, or installed user state. System planning may realize a Nix store derivation for comparison,
but never activates it.

## Reference and Contracts

- [Operations](../../operations.md)
- [Recovery](../../recovery.md)
- [Task Reference](../../task-reference.md)

## Validation Evidence

- `python3 -m unittest -v tests.test_user_convergence` — failed before the shared command-plan module existed, then
  passed after implementation.
- `python3 -m unittest -v tests.test_user_convergence tests.test_migration_behavior tests.test_ownership_boundary` —
  passed.
- `python3 -m py_compile .mise/lib/user_convergence.py tests/test_user_convergence.py tests/test_ownership_boundary.py`
  — passed.
- `uv run scripts/check-docs.py` — passed.
- `mise -E dev run check` — passed.

## Design Reconciliation

### Delivered as Designed

- Added a tested, stdlib-only user-convergence command-plan builder.
- Centralized user plan/apply command construction and force-dotfile argument handling.
- Added parity coverage for default and explicit force behavior, command substitutions, user task adapters, and aggregate
  plan forwarding.
- Updated operations, recovery, and task reference pages with default no-force and explicit force preview/apply flow.

### Intentional Changes

- Specification review clarified that parity applies for the same flags: default no-force and explicit force are each
  consistent between plan and apply.
- Package, repository-trust, and finalization differences are documented mode-specific execution substitutions rather
  than new package-manager dry-run behavior.

### Deferred Work

None.

### Rejected or Removed Scope

- No package-manager dry-run capabilities were added.
- No production privilege, deployment, inventory, or ownership behavior changed outside user command construction.

## Documentation Updated

- `docs/operations.md`
- `docs/recovery.md`
- `docs/task-reference.md`
- `docs/src/features/maison-012-plan-apply-parity/design.md`
- `docs/src/features/maison-012-plan-apply-parity/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation task: `maison-mol-88b`, commit `a7564c0`.
- Implementation coordinator: `maison-mol-bmj`.
- Parity-contract task: `maison-mol-bmj.1`, commit `b2e8227`.
- Parity-implementation task: `maison-mol-bmj.2`, commit `100dd31`.
- Documentation reconciliation task: `maison-mol-oov`.
- Validation task: `maison-mol-5it`.
