# MAISON-007: Parser-backed TOML mutations

## Delivery Summary

- Beads feature root: `maison-mol-ywg`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison now edits TOML through a parser-backed mutation helper instead of hand-written section splicing. Tool, package,
app, lockfile, and host-inventory mutations parse the complete target document, apply typed changes, validate the edited
TOML, and only then replace the candidate file.

The helper uses a checked-in `tomlkit` 0.13.3 wheel and verifies its SHA-256 digest before import. This keeps repair
commands available when normal mise project tool resolution is skipped or broken and avoids relying on ambient Python
site-packages.

## User-Facing Behavior

Operators continue using the existing `maison` and mise task commands. Supported comments, quoted keys, table
boundaries, arrays of tables, and CRLF line endings are preserved when Maison edits TOML. Malformed or unsupported TOML
fails with an error before Maison rewrites the file.

`host:add` uses the same parser-backed mutation layer for the active public or overlay inventory, then continues to
validate the full candidate inventory before committing the change.

## Design Integration

The implementation keeps Maison's existing ownership split: Nix/Lix still owns privileged system state, and mise-owned
commands continue to manage user tools, packages, apps, and inventory authoring. Shell task transaction wrappers and
command names were preserved; the parser-backed helper replaced only the TOML mutation internals.

The pinned runtime is repository-controlled and verified locally, matching the bootstrap trust model without adding a
new package manager, service, or privileged helper.

## Operational Impact

Configuration repair paths are safer. `tool:add` and `tool:remove` continue to work on the `--skip-tools` path, even
when invalid tool configuration would prevent normal mise project resolution. Failed parses, unsupported structures,
validation failures, or package-manager failures leave repository files unchanged through the existing transaction
wrappers.

## Reference and Contracts

- [Developer tooling](../../development/tooling.md)
- [Task Reference](../../task-reference.md)
- [Adding a Tool](../../add-a-tool.md)
- [Adding an App](../../add-an-app.md)

## Validation Evidence

- `python3 -m py_compile .mise/lib/config_edit.py tests/test_config_edit.py tests/test_topology.py` — passed.
- `python3 -m unittest -v tests.test_config_edit tests.test_topology.TransactionBehaviorTest` — passed.
- `shellcheck -x .mise/tasks/host/add` — passed.
- `uv run scripts/check-docs.py` — passed.
- `mise -E dev run check` — passed.

## Design Reconciliation

### Delivered as Designed

- Added a regression corpus for trailing table comments, quoted keys, arrays of tables, CRLF input, malformed TOML,
  lockfile edits, host inventory additions, and unrelated following sections.
- Replaced TOML table and lockfile text splicing in `.mise/lib/config_edit.py` with parser-backed edits.
- Added a host inventory mutation operation and routed `host:add` through it.
- Vendored and verified the pinned `tomlkit` runtime used by mutation scripts.
- Updated reader-facing documentation for the mutation guarantees and contributor runtime.

### Intentional Changes

- The specification was corrected during start-feature review to name `docs/src/development/tooling.md` for contributor
  tooling documentation while keeping root-level included command pages for task, tool, and app guidance.

### Deferred Work

None.

### Rejected or Removed Scope

- No new command surface was added.
- Non-TOML authoring artifacts remain outside this feature.
- The feature did not add a Rust helper or a privileged mutation service.

## Documentation Updated

- `docs/src/development/tooling.md`
- `docs/task-reference.md`
- `docs/add-a-tool.md`
- `docs/add-an-app.md`
- `docs/src/features/maison-007-parser-backed-toml-mutations/design.md`
- `docs/src/features/maison-007-parser-backed-toml-mutations/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation task: `maison-mol-nxg`, commit `ef9fde6`.
- Implementation coordinator: `maison-mol-imq`.
- Contract-test task: `maison-mol-imq.1`, commit `da88a62`.
- Parser implementation task: `maison-mol-imq.2`, commit `dfb7a7f`.
- Documentation reconciliation task: `maison-mol-0zx`.
- Validation task: `maison-mol-oyr`.
