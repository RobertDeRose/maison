# MAISON-011: Bounded deterministic test suite

## Delivery Summary

- Beads feature root: `maison-mol-8mr`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison's Python regression suite is now bounded and organized by subsystem. Tests that execute external commands use a
shared stdlib helper with timeouts, process-group cleanup, captured stdout/stderr, and truncated diagnostics. The former
monolithic topology test file has been split into focused modules for deployment, inventory, migration, ownership,
repository, and transaction behavior.

## User-Facing Behavior

Operators keep using the same `maison check` and mise task surfaces. Contributors get deterministic `check:tests`
behavior, focused subsystem commands, and clearer diagnostics when subprocess-backed tests fail or time out.

## Design Integration

The implementation keeps all changes in the test and documentation layer. It does not change Maison runtime behavior,
Nix/Lix system ownership, mise user ownership, supported platforms, deployment privilege boundaries, overlay behavior,
or inventory validation semantics. The subprocess helper is Python stdlib-only and test-local.

## Operational Impact

`mise run check:tests` runs Python `unittest` discovery over `tests/test_*.py` and is expected to complete within five
minutes on a warm supported development checkout. Test subprocesses default to a 30 second timeout; longer per-call
budgets must be explicit and no longer than 300 seconds.

## Reference and Contracts

- [Operations](../../operations.md)
- [Developer tooling](../../development/tooling.md)
- [Tooling reference](../../reference/tooling.md)

## Validation Evidence

- `python3 -m unittest -v tests.test_process_helper` — failed before helper implementation, then passed.
- `python3 -m py_compile tests/support/processes.py tests/test_process_helper.py` — passed.
- `mise -E dev run check` — passed after helper implementation.
- `python3 -m py_compile tests/*.py tests/support/*.py` — passed after subsystem split.
- `python3 -m unittest discover -s tests -p 'test_*.py' -v` — passed.
- Focused subsystem command covering process helper, inventory, deployment, migration, ownership, repository, mutation,
  and transaction modules — passed.
- `uv run scripts/check-docs.py` — passed.
- `mise -E dev run check` — passed.
- Final `mise -E dev run check:tests` after split cleanup — passed.

## Design Reconciliation

### Delivered as Designed

- Added `tests/support/processes.py` with a 30 second default timeout, 300 second maximum, process-group cleanup where
  supported, stdout/stderr capture, diagnostic truncation, and temporary-directory support.
- Added focused helper tests for success, failure diagnostics, environment/cwd handling, timeout cleanup, and timeout
  bounds.
- Split topology coverage into subsystem modules:
  - `tests/test_deployment_contracts.py`
  - `tests/test_inventory_behavior.py`
  - `tests/test_migration_behavior.py`
  - `tests/test_ownership_boundary.py`
  - `tests/test_repository_contracts.py`
  - `tests/test_transaction_behavior.py`
- Moved shared topology test helpers into `tests/support/topology.py`.
- Migrated test subprocess execution to the shared bounded helper.
- Updated operations, development tooling, and tooling reference docs with the bounded-suite contract.

### Intentional Changes

- Specification review corrected documentation impact paths to mdBook source pages under `docs/src/`.
- The implementation retained historical delivered-feature records that mention former `tests/test_topology.py` evidence
  because those records are audit history, not current validation instructions.

### Deferred Work

None.

### Rejected or Removed Scope

- No test framework replacement was introduced.
- No production code was rewritten solely for test organization.
- No deployment, Nix, or inventory coverage was removed.

## Documentation Updated

- `docs/operations.md`
- `docs/src/development/tooling.md`
- `docs/src/reference/tooling.md`
- `docs/src/features/maison-011-deterministic-test-suite/design.md`
- `docs/src/features/maison-011-deterministic-test-suite/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation task: `maison-mol-9hm`, commit `be3a910`.
- Implementation coordinator: `maison-mol-0dm`.
- Test-helper task: `maison-mol-0dm.1`, commit `27449b0`.
- Test-suite-split task: `maison-mol-0dm.2`, commit `2fd4af3`.
- Documentation reconciliation task: `maison-mol-524`.
- Validation task: `maison-mol-4wa`.
