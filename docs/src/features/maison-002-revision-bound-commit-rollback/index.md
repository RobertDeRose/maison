# MAISON-002: Revision-bound commit and rollback

## Delivery Summary

- Beads feature root: `maison-mol-quq`
- Status: delivered
- Pull request: not used for merge-mode delivery
- Merge commit: fast-forward delivery; final target SHA is recorded in the Beads delivery record
- Design record: [design.md](design.md)

## Delivered Capability

Deployment repository transactions now verify revision expectations during finalize and recovery to make repository state
transitions rollback-safe and restart-recoverable.

The root-owned helper now:

- records expected old/new revisions and destination path before finalize,
- verifies those revisions before commit or rollback,
- performs rollback using a temporary rescue path instead of deleting the live repository first,
- and executes startup recovery of incomplete transactions before continuing with user convergence.

## User-Facing Behavior

- Each staged repository transaction writes expected old/new revision metadata into `active.json` and journal events.
- Deployment rejects commit when the active repository revision has drifted from the expected prior revision after
  staging.
- Deployment rejects finalization when the candidate revision does not match the staged revision recorded at stage time.
- `maison deploy` recovers incomplete remote repository transactions before user convergence resumes.
- Rollback preserves a recoverable repository path during replacement.

## Design Integration

MAISON-002 extends MAISON-001's root-owned transaction architecture with revision contracts, non-destructive finalize
semantics, and startup recovery. Deploy-rs system rollback behavior and public command surface (`maison deploy <host>`) are
unchanged.

## Reference and Contracts

- [Remote deployment](../../deployment.md)
- [Recovery](../../recovery.md)
- [Operations](../../operations.md)
- [Migration contract](../../migration-contract.md)
- [Architecture](../../architecture.md)
- [Task reference](../../task-reference.md)

## Operational Impact

Operators inspect root-owned transaction state under
`/home/.maison-deploy/transactions/<user>/<repo-hash>/` as needed. The transaction state files are:

- `transaction.lock` for serialization,
- `active.json` for current in-flight transaction metadata,
- `<transaction-id>/journal.jsonl` for durable journal events,
- `<transaction-id>/staging/repository` for extracted archive contents,
- `<transaction-id>/rollback/repository` for the replacement when a previous repository exists.

## Design Reconciliation

### Delivered as Designed

- Revision checks are enforced before commit/rollback and before startup recovery decisions.
- Root-owned rollback no longer deletes the active repository before a replacement is proven safe.
- Recovery from incomplete state uses the recorded journal and revision information.

### Deferred Work

- Additional command-line inspection surfaces (`inspect`, `abort`, explicit `recover`) remain planned for future ergonomics
  while preserving MAISON-002 scope.

## Documentation Updated

- `docs/deployment.md`
- `docs/recovery.md`
- `docs/operations.md`
- `docs/task-reference.md`
- `docs/src/features/maison-002-revision-bound-commit-rollback/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation task: `maison-mol-0a9`.
- Revision-contract and engine implementation tasks: `maison-mol-j0h.1`, `maison-mol-j0h.2`.
- Validation task: `maison-mol-0kt`.

## Validation Evidence

- `python3 -m unittest -v tests.test_deploy_transaction` — passed for transaction path contract tests.
- `python3 -m unittest -v tests.test_topology.DeploymentContractTest` — passed for revision and recovery contract tests.
- `uv run scripts/check-docs.py` — passed after documentation updates.
- `mise -E dev run check` — passed.
