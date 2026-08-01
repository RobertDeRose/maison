# MAISON-010: Shared inventory schema validation

## Delivery Summary

- Beads feature root: `maison-mol-bvr`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison now has a checked-in public inventory schema contract at `schemas/inventory.toml`. Python and Nix validation both
load that contract for supported systems, profile names, feature keys, deploy keys, and deploy defaults. A shared fixture
corpus under `tests/fixtures/inventory/` exercises valid public and overlay shapes plus invalid drift cases so CI fails
when the validators disagree.

## User-Facing Behavior

Operators keep using the same `maison host validate`, planning, deployment, and bootstrap flows. Inventory errors are
now governed by one documented field/default contract rather than separately maintained Python and Nix constants. Unknown
feature keys, unknown deploy fields, duplicate profiles, deploy path escapes, and value type mismatches are rejected
consistently before deployment or authoring changes can proceed.

## Design Integration

The implementation keeps Python as the ergonomic typed inventory reader while Nix imports the same schema data with
`builtins.fromTOML` before constructing outputs. The Nix-packaged `maison-inventory` app sets `MAISON_INVENTORY_SCHEMA`
so the Python helper can find the schema from the Nix store. This preserves the existing Nix/Lix system and mise user
ownership boundary while replacing duplicated validation constants with one public contract.

Overlay behavior remains replacement-based rather than merged: when an overlay inventory is active, Maison validates
that inventory and its sibling `hosts/` override layout. Host override directories must correspond to inventory hosts and
may contain only `system.nix`.

## Operational Impact

Inventory contract changes now require updating `schemas/inventory.toml` and the shared fixtures. The new
[Inventory Reference](../../reference/inventory.md) documents supported fields, defaults, constraints, and overlay
validation behavior for operators and contributors.

## Reference and Contracts

- [Architecture](../../architecture.md)
- [Add a Host](../../add-a-host.md)
- [Remote Deployment](../../deployment.md)
- [Inventory Reference](../../reference/inventory.md)
- [Tooling Reference](../../reference/tooling.md)

## Validation Evidence

- `python3 -m py_compile tests/test_inventory_schema.py` — passed before fixture commit.
- `python3 -m unittest -v tests.test_inventory_schema` — failed as expected before implementation because Nix still
  accepted drift cases; passed after implementation.
- `python3 -m py_compile .mise/lib/inventory.py tests/test_inventory_schema.py tests/test_topology.py` — passed.
- `python3 -m unittest -v tests.test_inventory_schema tests.test_topology.InventoryBehaviorTest tests.test_topology.OverlayContractTest tests.test_topology.RepositoryContractTest` — passed.
- `uv run scripts/check-docs.py` — passed.
- `mise -E dev run check` — passed.

## Design Reconciliation

### Delivered as Designed

- Added `schemas/inventory.toml` as the single public inventory schema contract.
- Updated Python inventory validation to load supported systems, profiles, feature defaults, deploy defaults, and regex
  policy from the schema.
- Updated Nix validation to import the same schema and reject duplicate profiles, unknown features, unknown deploy
  fields, and deploy value type mismatches.
- Added shared valid and invalid inventory fixtures consumed by both Python and Nix validation tests.
- Added an inventory reference page and updated architecture, host authoring, deployment, tooling, and navigation docs.

### Intentional Changes

- Specification review replaced ambiguous overlay merge wording with active overlay inventory and host override layout
  fixture coverage, matching MAISON-004 behavior.
- The Nix-packaged inventory app exports `MAISON_INVENTORY_SCHEMA` so the Python helper remains usable when copied into
  the Nix store.

### Deferred Work

None.

### Rejected or Removed Scope

- The feature does not replace TOML as the inventory format.
- The public fixture corpus contains only neutral examples and no private inventory.
- Overlay inventories are not merged with the public inventory.

## Documentation Updated

- `docs/architecture.md`
- `docs/add-a-host.md`
- `docs/deployment.md`
- `docs/src/reference/inventory.md`
- `docs/src/reference/tooling.md`
- `docs/src/features/maison-010-shared-inventory-schema/design.md`
- `docs/src/features/maison-010-shared-inventory-schema/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation task: `maison-mol-41t`, commit `05ca64e`.
- Implementation coordinator: `maison-mol-8ey`.
- Schema-fixtures task: `maison-mol-8ey.1`, commit `d96b24a`.
- Schema-implementation task: `maison-mol-8ey.2`, commit `692bfca`.
- Documentation reconciliation task: `maison-mol-4np`.
- Validation task: `maison-mol-50d`.
