# MAISON-013: Exact dotfile backup manifests

## Delivery Summary

- Beads feature root: `maison-mol-h8e`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison now creates exact, manifest-backed snapshots before an explicitly forced dotfile handoff. Snapshots preserve
whether every refused target is a file, directory, or symlink, without dereferencing a symlink target.

## User-Facing Behavior

Forced handoff remains opt-in:

```bash
maison user plan --force-dotfiles
maison user apply --force-dotfiles
```

Each handoff writes `manifest.json` in its timestamped dotfile backup directory. To restore its pending entries, use:

```bash
maison user restore-dotfiles ~/.local/state/maison/backups/dotfiles/<timestamp> --force
```

The explicit force flag is required before a restore can replace a current target. A restore stops at its first failure;
completed entries are recorded as `restored`, so rerunning restores only remaining `pending` entries.

## Design Integration

`.mise/lib/dotfile_backups.py` is a Python-stdlib helper called by the existing user preparation adapter and the restore
task. It validates paths under the managed home and Maison backup root, snapshots by `lstat` object identity, preserves
file and directory metadata, recreates symlinks by their literal target, and refuses sockets, FIFOs, block devices, and
character devices. Nix/Lix remains responsible for system state; mise remains the user-convergence boundary.

## Operational Impact

Inspect a backup's `manifest.json` before restoring it. Manifest paths and payload paths are containment-validated; a
malformed, escaping, or missing payload is rejected before that entry can replace a target. Existing application-bundle
backup archival and legacy Git configuration migration behavior are unchanged.

## Reference and Contracts

- [Operations](../../operations.md)
- [Recovery](../../recovery.md)
- [Task Reference](../../task-reference.md)

## Validation Evidence

- `python3 -m unittest -v tests.test_dotfile_backups tests.test_migration_behavior tests.test_repository_contracts.RepositoryContractTest.test_task_and_script_entrypoints_are_executable` — passed.
- `python3 -m py_compile .mise/lib/dotfile_backups.py tests/test_dotfile_backups.py tests/test_migration_behavior.py` — passed.
- `uv run scripts/check-docs.py` — passed.
- `mise -E dev run check` — passed (129 tests, shell task validation, and Nix checks).

## Design Reconciliation

### Delivered as Designed

- Added atomic versioned JSON manifests with source path, object type, mode, timestamps, payload path, symlink target,
  and restoration status.
- Added exact backup and restore coverage for files, directories, symlinks, unsupported objects, escaping manifests,
  required force, and partial restoration progress.
- Added force-gated `user:restore-dotfiles` and standalone operational recovery instructions.

### Intentional Changes

- Specification review selected the explicit `maison user restore-dotfiles <backup-directory> --force` interface.
- The existing shell task retains conflict discovery and delegates stateful snapshot/restore behavior to the tested
  Python helper.

### Deferred Work

None.

### Rejected or Removed Scope

- No unmanaged directory backup support was added.
- No application-bundle archive behavior was changed.
- No Nix/Lix system ownership, private inventory, or deployment behavior changed.

## Documentation Updated

- `docs/operations.md`
- `docs/recovery.md`
- `docs/task-reference.md`
- `docs/src/features/maison-013-dotfile-backup-manifests/design.md`
- `docs/src/features/maison-013-dotfile-backup-manifests/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation: `maison-mol-c8i`, commit `572a77b`.
- Backup contract: `maison-mol-xg1.1`, commit `4a98bdf`.
- Backup implementation: `maison-mol-xg1.2`, commit `ec9f1bb`.
- Documentation reconciliation: `maison-mol-3kb4`.
- Validation: `maison-mol-f89l`.
