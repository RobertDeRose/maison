# MAISON-001: Root-owned deployment transaction state

## Delivery Summary

- Beads feature root: `maison-mol-6y0`
- Status: delivered
- Pull request: not used for merge-mode delivery
- Merge commit: fast-forward delivery; final target SHA is recorded in the Beads delivery record
- Design record: [design.md](design.md)

## Delivered Capability

Remote repository deployment now keeps privileged transaction state outside the managed user's home. Maison stages
committed repository archives through a stdlib Python transaction manager that creates a root-owned same-filesystem
transaction namespace, unpredictable transaction IDs, a single lock, an active state file, a journal, staging storage,
and rollback storage.

The public deploy command remains `maison deploy <host>` / `mise run deploy <host>`. The shell task streams the Python
helper to the remote host, stages the repository archive, runs user convergence, then commits or rolls back the
repository transaction.

## User-Facing Behavior

- Safe default transaction root for `/home/<managed-user>/.maison` is
  `/home/.maison-deploy/transactions/<managed-user>/<repo-hash>/`.
- Deployment fails clearly if transaction state is under the managed home, crosses filesystems, uses unsafe symlinks,
  has unexpected ownership, or is group/world writable.
- Deployment fails clearly for unsupported or tampered archives, including missing required repository files, invalid
  revision stamps, `.git` directories, path traversal, and symlink or special-file archive members.
- Failed user convergence rolls back from the root-owned transaction state. If rollback state is missing or unsafe,
  Maison leaves the active repository in place and preserves `active.json` for operator inspection.

## Design Integration

The implementation preserves Maison's two-layer architecture: deploy-rs still owns Linux system profile deployment and
rollback, while Maison owns repository staging and mise user convergence. The privileged repository transaction boundary
is now explicit: journals, locks, staging trees, rollback trees, and active state are root-owned state outside the
managed user's writable home.

MAISON-001 intentionally provides the root-owned transaction and journal foundation. Revision-bound startup recovery,
fsync-complete non-destructive transitions, and richer inspect/abort command surfaces remain assigned to MAISON-002.

## Operational Impact

Operators inspect incomplete repository transactions under the root-owned transaction root rather than next to the
managed repository. The durable state files are:

- `transaction.lock` for serialization;
- `active.json` for the current incomplete transaction;
- `<transaction-id>/journal.jsonl` for journal events;
- `<transaction-id>/staging/repository` for extracted staged content before install;
- `<transaction-id>/rollback/repository` for the previous repository when one existed.

## Reference and Contracts

- [Remote deployment](../../deployment.md)
- [Recovery](../../recovery.md)
- [Architecture](../../architecture.md)
- [Migration contract](../../migration-contract.md)
- [Task reference](../../task-reference.md)
- [Tooling reference](../../reference/tooling.md)

## Validation Evidence

- `python3 -m unittest -v tests.test_deploy_transaction` — passed for transaction path contract tests.
- `python3 -m unittest -v tests.test_deploy_transaction tests.test_topology.DeploymentContractTest` — passed for
  transaction contract and deployment behavior tests.
- `uv run scripts/check-docs.py` — passed after documentation changes.
- `mise -E dev run check` — passed after final implementation changes.

## Design Reconciliation

### Delivered as Designed

- Root-owned, same-filesystem transaction state replaces managed-home sidecars.
- Transaction IDs are unpredictable and path-safe.
- Transaction roots reject managed-home placement, symlinks, wrong owners, unsafe modes, and cross-filesystem roots.
- Repository deployment uses a single lock, journal, active state record, staging tree, and rollback tree.
- Stateful deployment behavior moved from shell into tested Python stdlib code.

### Intentional Changes

- The delivered command surface exposes `stage` and `finalize`; `abort` and `inspect-incomplete` remain documented as
  MAISON-002 follow-up surface because MAISON-001's reviewed scope is the transaction root and journal foundation.
- A validation-blocking tooling scaffold defect was fixed in `maison-0lpv` on this branch: unsupported Intel macOS
  references were removed from tooling docs and locks so the full repository suite could pass.

### Deferred Work

- MAISON-002 owns revision-bound startup recovery and stronger non-destructive commit/rollback semantics.
- MAISON-003 owns restricting remote deployment privileges beyond the current root-owned state boundary.

### Rejected or Removed Scope

- Legacy `<repo>.next.<pid>`, `<repo>.previous`, and `<repo>.deploy-state` sidecars are no longer supported behavior.
- Maison does not fall back to managed-user-controlled transaction state when root-owned same-filesystem state is
  unavailable.

## Documentation Updated

- `README.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/migration-contract.md`
- `docs/recovery.md`
- `docs/task-reference.md`
- `docs/src/features/maison-001-root-owned-deployment-transactions/design.md`
- `docs/src/features/maison-001-root-owned-deployment-transactions/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation: `e1f5c8a` (`docs(features): reconcile MAISON-001 specification`).
- Validation blocker chore: `48a781a` (removed unsupported Intel macOS scaffold targets, Beads `maison-0lpv`).
- Contract and documentation task: `ae664b3` (`test(deploy): define root-owned transaction contract`, Beads
  `maison-mol-xjt.1`).
- Engine implementation task: `b0ccaf7` (`feat(deploy): use root-owned repository transactions`, Beads
  `maison-mol-xjt.2`).
- Implementation coordinator `maison-mol-xjt` closed after both implementation children and final validation passed.
