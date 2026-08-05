# MAISON-004: Private overlay configuration split

> Historical record: this delivery was superseded by the single consumer-root model. The old source-selection state and
> command paths described below are not supported; current migration guidance is in [Migration Contract](../../migration-contract.md).

## Delivery Summary

- Beads feature root: `maison-mol-e9t`
- Status: delivered, later superseded by `maison-hi8`
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison now separates public reusable vehicle code from private site configuration. The public repository keeps neutral
starter inventory, host examples, package files, dotfiles, validators, Nix modules, and task machinery. A tracked private
overlay repository can own real hosts, usernames, emails, deploy targets, package declarations, dotfile overrides, and
trusted key material.

Bootstrap accepts `--overlay <git-url-or-path>`, records the selected source in local XDG state, and clones or updates
the overlay into a standard XDG data path. When the overlay contains `inventory.toml`, Maison uses that typed inventory
and its sibling `hosts/` tree for shell task lookups, Python validation, Nix evaluation, host mutation, and deployment
targeting.

## User-Facing Behavior

Operators keep using the existing Maison command surface. Fresh setup can provide an overlay explicitly:

```bash
./bootstrap.sh --host "$(hostname -s)" --overlay GIT-URL-OR-PATH
```

Overlay source precedence is:

1. `--overlay <git-url-or-path>` for the current bootstrap run.
2. `MAISON_OVERLAY_SOURCE`, including a value supplied by mise secrets.
3. `${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml`.

The standard clone/update path is `${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay`. Interactive setup may prompt
when overlay input is required; non-interactive setup fails clearly instead of silently continuing with public starter
data for a real machine.

## Design Integration

The implementation preserves Maison's two-layer architecture. Nix/Lix remains the privileged system owner and mise
remains the user-state owner. The overlay is a data source for the same typed inventory and layout contracts; it is not
a second command surface or arbitrary schema framework.

Public Maison remains a valid starter repository. Private overlays mirror supported owned data paths such as
`inventory.toml`, `hosts/`, `config/mise/*.toml`, `dotfiles/`, and trusted key files.

## Operational Impact

Operators can recover overlay selection by restoring or recreating the XDG state file, or by rerunning bootstrap with
`--overlay`. If the overlay clone is corrupt, it can be moved aside and recloned from the recorded source.

`maison host add` mutates the active inventory repository. With an overlay inventory, new inventory entries and optional
host override stubs are written to the overlay clone rather than to public Maison.

## Reference and Contracts

- [Architecture](../../architecture.md)
- [Operations](../../operations.md)
- [Remote deployment](../../deployment.md)
- [Recovery](../../recovery.md)
- [Package policy](../../package-policy.md)
- [Task reference](../../task-reference.md)
- [Adding a Host](../../add-a-host.md)
- [Adding a Tool](../../add-a-tool.md)
- [Adding an App](../../add-an-app.md)

## Validation Evidence

- `python3 -m py_compile scripts/maison_overlay.py tests/test_topology.py .mise/lib/inventory.py` — passed.
- `python3 -m unittest -v tests.test_topology.OverlayContractTest` — passed.
- `uv run scripts/check-docs.py` — passed.
- `mise -E dev run check` — passed.

## Design Reconciliation

### Delivered as Designed

- Bootstrap supports `--overlay` and hands the selected source to the bootstrap task.
- Overlay state uses `${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml`.
- Overlay clones use `${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay`.
- `--overlay` takes precedence over environment and saved state sources.
- The same typed TOML inventory validator handles public examples and private overlay fixtures.
- Python task lookups, Nix evaluation, host overrides, and deployment targeting use the active overlay inventory when
  present.
- Public starter inventory, dotfiles, and reader examples no longer contain personal infrastructure identity.

### Intentional Changes

- The first implementation introduced a small tested Python helper at `scripts/maison_overlay.py` plus a thin shell
  adapter at `.mise/lib/overlay.sh`, matching the design preference for Python stdlib state handling while preserving
  shell task compatibility.
- Public starter data remains usable for validation and examples, but real machine convergence is documented around an
  overlay rather than public defaults.

### Deferred Work

- Overlay layering for every possible `config/mise/*.toml` and `dotfiles/` application path remains limited to the
  documented mirrored layout and active inventory behavior delivered here. Future features can expand mutation surfaces
  if needed.

### Rejected or Removed Scope

- Public Maison no longer carries personal usernames, hostnames, email addresses, deploy endpoints, or trusted signing
  keys.
- Untracked-only local inventory is not the durable source of truth; the private overlay repository is tracked.

## Documentation Updated

- `README.md`
- `docs/add-a-host.md`
- `docs/add-a-tool.md`
- `docs/add-an-app.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/operations.md`
- `docs/package-policy.md`
- `docs/recovery.md`
- `docs/task-reference.md`
- `docs/src/features/maison-004-private-overlay-configuration/design.md`
- `docs/src/features/maison-004-private-overlay-configuration/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation task: `maison-mol-luq`, commit `4d88caa`.
- Implementation coordinator: `maison-mol-z6x`.
- Overlay contract task: `maison-mol-z6x.1`, commit `96136b0`.
- Overlay loader task: `maison-mol-z6x.2`, commit `8ae4710`.
- Overlay docs/examples task: `maison-mol-z6x.3`, commit `8d5c240`.
- Documentation reconciliation task: `maison-mol-5is`.
- Validation task: `maison-mol-uie`.
