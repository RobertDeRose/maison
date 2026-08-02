# Copier-backed overlay setup and bootstrap onboarding

## Delivery Summary

- Beads feature root: `maison-mol-5s9`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: `14a5e92` (fast-forward target)
- Design record: [design.md](design.md)

## Delivered Capability

Maison now treats private-overlay creation as a first-class bootstrap workflow. `examples/template/` is a Copier
template that renders a private inventory, policy stubs, dotfile guidance, Copier answers, and a first-copy host setup
task. Bootstrap seeds the inventory username from the current effective user; the task delegates host registration and
supported-platform detection to Maison's validated `host:add` command.

Bootstrap accepts `--overlay` or the canonical `MAISON_OVERLAY` environment variable. Existing local Git repositories
are used directly; remote sources retain the standard clone/update behavior. When no overlay is available, interactive
users can choose immediate Copier setup. Declining setup installs and links the Maison CLI but skips Nix and system/user
activation and prints the documentation path for later setup.

## User-Facing Behavior

Explicit setup:

```bash
MAISON_OVERLAY=GIT-URL-OR-PATH ./bootstrap.sh --host "$(hostname -s)"
```

Manual template setup from a Maison checkout:

```bash
mise install uv
MAISON_HOME="$PWD" MAISON_HOST="$(hostname -s)" \
  mise exec -- uvx --from copier copier copy --trust \
    --data "username=$(id -un)" examples/template "$HOME/src/my-maison-overlay"
```

The legacy `MAISON_OVERLAY_SOURCE` environment variable remains accepted as a compatibility fallback. Manual Copier
runs can seed the username with `--data "username=$(id -un)"`. `MAISON_REQUIRE_OVERLAY=true` keeps the non-interactive
missing-overlay failure mode. `copier update --trust` does not rerun host registration.

## Design Integration

The feature keeps Maison's ownership boundary intact: Maison owns the framework, schema, bootstrap orchestration, and
mutation task; the generated private repository owns user/site inventory and configuration. Overlay state remains in the
owner-only XDG state file. Inventory mutation continues through `mise run host:add`, preserving repository locks,
validation, supported-system checks, and rollback behavior. Copier is installed ephemerally through Maison-managed `uv`.

## Operational Impact

First-run immediate setup needs network access for `uvx copier` and normal Git credentials. The generated repository is
initialized as a Git authoring checkout, but publishing a remote and committing/pushing policy remain user decisions.
A user who declines setup can follow the printed README/template guidance and rerun bootstrap with `--overlay` or
`MAISON_OVERLAY`.

## Reference and Contracts

- [Operations](../../operations.md)
- [Adding a host](../../add-a-host.md)
- [Tooling reference](../../reference/tooling.md)
- [Architecture](../../architecture.md)
- [Feature design](design.md)

## Validation Evidence

- `python3 -m unittest tests.test_copier_template tests.test_inventory_behavior` — passed: 18 focused tests.
- `bash -n` and `shellcheck` for bootstrap and generated host setup scripts — passed.
- `ruff check` and `ruff format --check` for changed Python files — passed.
- `uv run scripts/check-docs.py` — passed.
- `mdbook build docs` — passed.
- `mise x -- hk check` — passed.
- `mise run check` — passed: 156 Python tests plus data, shell, TypeScript, and Nix checks.
- No real system activation, remote repository mutation, or host deployment was performed.

## Design Reconciliation

### Delivered as Designed

- Replaced static overlay-copy guidance with a Copier template.
- Added `MAISON_OVERLAY` and preserved explicit `--overlay` precedence and saved-state behavior.
- Added interactive immediate/deferred onboarding with a safe no-activation path.
- Delegated generated host setup to Maison's existing `host:add` task.
- Added direct local Git overlay support while retaining remote clone/update behavior.
- Added deterministic template, bootstrap, source-precedence, and no-activation tests.

### Intentional Changes

- `MAISON_OVERLAY_SOURCE` is compatibility-only; new documentation uses `MAISON_OVERLAY`.
- Declining first-run setup is a successful CLI-only bootstrap rather than neutral starter activation.
- Local overlay paths are recorded and used directly instead of copied to the standard XDG clone directory.

### Deferred Work

- Pull-request and merge metadata remain pending the explicit delivery action selected after close-out.
- Real host activation remains outside the available validation environment.
- Creating or publishing a private remote repository remains a user-controlled operation.

### Rejected or Removed Scope

- No automatic GitHub repository creation.
- No secrets, private keys, or real identity values in the public template.
- No duplicate inventory mutation implementation in the Copier template.
- No new supported platforms or changes to Nix/mise ownership boundaries.

## Documentation Updated

- `README.md`
- `docs/operations.md`
- `docs/add-a-host.md`
- `docs/src/reference/tooling.md`
- `examples/template/README.md`
- `examples/template/dotfiles/README.md`
- `docs/src/SUMMARY.md`
- `docs/src/planned-features.md`
- `docs/src/features/maison-overlay-copier-bootstrap/design.md`
- `docs/src/features/maison-overlay-copier-bootstrap/index.md`
- `docs/src/features/index.md`

## Audit Trail

- Planning and reviewed design: `maison-mol-5s9`, commit `8cbd6eb`.
- Copier template and generated host setup: `maison-mol-xke.2`, commit `e7b2c11`.
- Bootstrap onboarding and overlay source behavior: `maison-mol-xke.1`, commit `246aceb`.
- Reader documentation: `maison-mol-xke.3`, commit `11f37a8`.
- Implementation coordinator: `maison-mol-xke`.
- Documentation reconciliation: `maison-mol-o13`.
- Validation: `maison-mol-2b5`.
- Holistic delivery review: `maison-mol-a2x`.
- Documentation drift review: `maison-mol-ecd`.
- Delivery action: `maison-mol-e0f`, merged into `main` at `14a5e92`.
