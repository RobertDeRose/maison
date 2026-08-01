# MAISON-008: Repository mutation locking and journals

## Delivery Summary

- Beads feature root: `maison-mol-4ev`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison now serializes local repository-writing authoring commands with a shared fail-fast `fcntl` lock. Tool, package,
app, host, and flake-lock update mutations acquire the target repository lock before reading mutable repository state,
recover incomplete local journals, stage candidate files, validate, and then replace repository files atomically.

The new local journal helper records original files, candidate files, validation state, commit state, and recovery action
for repository file mutations. If recovery or rollback fails, Maison returns non-zero and preserves the journal and
copied state for diagnostics instead of suppressing the failure.

## User-Facing Behavior

Operators continue using the existing `maison` and mise task names. If another repository mutation is active for the
same public checkout or private overlay, the second command fails fast and identifies the busy repository and journal
location. Read-only plan, status, list, validate, and search commands do not take the mutation lock.

Affected repository-writing commands are `tool:add`, `tool:remove`, `package:add`, `package:remove`, `app:add`,
`app:remove`, `host:add`, and `update`.

## Design Integration

The implementation keeps the Nix/Lix system and mise user ownership boundary unchanged. Local authoring transactions
remain in the user layer and are implemented with Python and shell task adapters. The local mutation journal is
explicitly separate from the root-owned remote deployment transaction namespace, so MAISON-001 and MAISON-002 deployment
transaction and rollback contracts remain intact.

Journal state is untracked local Maison state keyed by the canonical target repository path. Tests may override the
state root with `MAISON_REPOSITORY_MUTATION_STATE_DIR`; normal operation uses
`${XDG_STATE_HOME:-$HOME/.local/state}/maison/repository-mutations/`.

## Operational Impact

Concurrent repository writes no longer race silently. Operators should wait for the active mutation to finish before
retrying a busy-lock failure. If a mutation is interrupted, rerunning a mutation for the same repository triggers the
startup recovery pass before the new command reads state.

Because journals may copy private overlay data, state directories use owner-only permissions. Operators should preserve
journals after rollback failures until the active files and copied originals/candidates are understood.

## Reference and Contracts

- [Architecture](../../architecture.md)
- [Operations](../../operations.md)
- [Recovery](../../recovery.md)
- [Task Reference](../../task-reference.md)

## Validation Evidence

- `python3 -m py_compile tests/test_repository_mutation.py` — passed before contract-test commit.
- `python3 -m py_compile .mise/lib/repository_mutation.py tests/test_repository_mutation.py tests/test_topology.py` — passed.
- `python3 -m unittest -v tests.test_repository_mutation tests.test_topology.TransactionBehaviorTest` — passed.
- `shellcheck -x .mise/lib/transaction.sh .mise/tasks/tool/add .mise/tasks/tool/remove .mise/tasks/package/add .mise/tasks/package/remove .mise/tasks/app/add .mise/tasks/app/remove .mise/tasks/host/add .mise/tasks/update` — passed.
- `uv run scripts/check-docs.py` — passed.
- `mise -E dev run check` — passed.

## Design Reconciliation

### Delivered as Designed

- Added a shared stdlib `fcntl` lock and local journal helper in `.mise/lib/repository_mutation.py`.
- Routed tool, package, app, host, and `flake.lock` update repository mutations through the shared lock.
- Added journal helpers in `.mise/lib/transaction.sh` and used them around multi-file and single-file repository
  replacements.
- Added contract tests for fail-fast locking, journal recovery states, rollback-failure diagnostics, mutating task
  surfaces, and read-only task exclusions.
- Updated architecture, operations, recovery, and task-reference documentation.

### Intentional Changes

- Specification review narrowed scope to repository-writing commands. Installed-state update commands such as
  `user:update`, `package:update`, and `app:update` remain outside the repository mutation lock because they do not edit
  checked-in or overlay repository files.
- Concurrent mutation semantics were made fail-fast rather than wait/block to keep the first implementation small and
  predictable.

### Deferred Work

None.

### Rejected or Removed Scope

- Read-only commands are not serialized.
- The feature does not replace Git as source history.
- The local authoring journal does not reuse or modify the root-owned remote deployment transaction namespace.

## Documentation Updated

- `docs/architecture.md`
- `docs/operations.md`
- `docs/recovery.md`
- `docs/task-reference.md`
- `docs/src/features/maison-008-repository-mutation-locking/design.md`
- `docs/src/features/maison-008-repository-mutation-locking/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation task: `maison-mol-0pc`, commit `6b168ba`.
- Implementation coordinator: `maison-mol-auy`.
- Contract-test task: `maison-mol-auy.1`, commit `f9b4151`.
- Lock/journal implementation task: `maison-mol-auy.2`, commit `9e6562d`.
- Documentation reconciliation task: `maison-mol-g1r`.
- Validation task: `maison-mol-bdn`.
