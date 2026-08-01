# MAISON-009: Authoring checkout guard

## Delivery Summary

- Beads feature root: `maison-mol-74l`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison now rejects repository-writing authoring commands when the target repository is a deployed runtime snapshot. A
snapshot is identified by `.maison-revision` without `.git`; it is safe for runtime plan, apply, status, deployment
finalization, and recovery, but not for source edits that the next deployment would overwrite.

## User-Facing Behavior

Authoring-only commands keep their existing names: `tool:add`, `tool:remove`, `package:add`, `package:remove`,
`app:add`, `app:remove`, `host:add`, and `update`. Before taking the local mutation lock, each command checks the
repository it will write for Git authoring evidence. Both normal `.git` directories and linked-worktree `.git` files are
accepted.

When the target is a deployed Maison snapshot, the command exits non-zero and directs the operator to edit from a Git
authoring checkout or private overlay repository. Read-only and runtime commands remain available without `.git`.

## Design Integration

The implementation reuses the MAISON-008 repository mutation helper instead of adding a new runtime. Checkout detection
uses only marker files, so it does not read mutable TOML, lockfiles, or journaled content before local mutation lock and
startup recovery logic run. `host:add` guards the active inventory repository, preserving MAISON-004 overlay behavior:
a deployed public Maison snapshot may still author hosts in a private overlay clone when that overlay is a Git checkout.

The feature keeps privileged system state in Nix/Lix and user/source authoring state in mise. It does not add `.git` to
remote deployment archives and does not weaken MAISON-001/002 root-owned remote deployment transaction contracts.

## Operational Impact

Operators should run repository-writing commands from the public Maison source checkout or the private overlay checkout
that owns the data being changed. Deployed snapshots are runtime trees; rejected authoring commands should be retried
from the durable source repository and then applied or deployed again.

## Reference and Contracts

- [Architecture](../../architecture.md)
- [Operations](../../operations.md)
- [Remote Deployment](../../deployment.md)
- [Recovery](../../recovery.md)
- [Task Reference](../../task-reference.md)

## Validation Evidence

- `python3 -m py_compile tests/test_repository_mutation.py` — passed before contract-test commit.
- `python3 -m unittest -v tests.test_repository_mutation.AuthoringCheckoutGuardTest tests.test_repository_mutation.RepositoryMutationTaskSurfaceTest tests.test_repository_mutation.MaisonCommandDeployedSnapshotTest` — failed as expected before implementation; passed after implementation.
- `python3 -m py_compile .mise/lib/repository_mutation.py tests/test_repository_mutation.py` — passed.
- `shellcheck -x .mise/lib/transaction.sh .mise/tasks/tool/add .mise/tasks/tool/remove .mise/tasks/package/add .mise/tasks/package/remove .mise/tasks/app/add .mise/tasks/app/remove .mise/tasks/host/add .mise/tasks/update` — passed.
- `python3 -m unittest -v tests.test_repository_mutation tests.test_topology.TransactionBehaviorTest` — passed.
- `uv run scripts/check-docs.py` — passed.
- `mise -E dev run check` — passed.

## Design Reconciliation

### Delivered as Designed

- Added a shared stdlib Python checkout detector in `.mise/lib/repository_mutation.py`.
- Added a shell adapter in `.mise/lib/transaction.sh` and called it from all repository-writing authoring tasks.
- Detected deployed snapshots as `.maison-revision` without `.git` and returned clear source/overlay guidance.
- Preserved runtime and read-only command behavior in gitless deployed snapshots.
- Kept `host:add` target-aware by checking the active inventory root instead of always checking public Maison.
- Updated reader-facing architecture, operations, deployment, recovery, and task-reference documentation.

### Intentional Changes

- Specification review narrowed the behavior to fail-fast rejection instead of dynamic task hiding.
- Test fixtures for mutating transaction behavior now include `.git` markers to model authoring repositories.

### Deferred Work

None.

### Rejected or Removed Scope

- Deployed snapshots still do not contain `.git`.
- Runtime plan, apply, status, deployment finalization, and recovery commands are not blocked by the authoring guard.
- The local authoring guard does not reuse or alter the root-owned remote deployment transaction namespace.

## Documentation Updated

- `docs/architecture.md`
- `docs/operations.md`
- `docs/deployment.md`
- `docs/recovery.md`
- `docs/task-reference.md`
- `docs/src/features/maison-009-authoring-checkout-guard/design.md`
- `docs/src/features/maison-009-authoring-checkout-guard/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation task: `maison-mol-her`, commit `73d882b`.
- Implementation coordinator: `maison-mol-kid`.
- Contract-test task: `maison-mol-kid.1`, commit `5ccf192`.
- Checkout-implementation task: `maison-mol-kid.2`, commit `b44fb98`.
- Documentation reconciliation task: `maison-mol-xe7`.
- Validation task: `maison-mol-zki`.
