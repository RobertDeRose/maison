# Copier-backed fresh consumer setup and bootstrap onboarding

> The former private-overlay runtime is retired, but the Copier template remains a supported setup-time starter for a
> fresh consumer repository. See [Consumer Repository Reference](../../reference/consumer.md).

## Delivery Summary

- Beads feature root: `maison-mol-5s9`
- Status: delivered; retained as the fresh-consumer setup scaffold
- Pull request: pending delivery action
- Merge commit: `14a5e92` (fast-forward target)
- Design record: [design.md](design.md)

## Delivered Capability

Maison retains `overlay_template/` as a Copier template that renders a consumer flake, inventory, mise policy, dotfile
guidance, Copier answers, and a first-copy host setup task. Bootstrap seeds the inventory username from the current
effective user; the task delegates host registration and supported-platform detection to Maison's validated `host:add`
command.

`bootstrap.sh --setup PATH` renders the template into a destination separate from Maison, creates the consumer lock, and
stops for review before activation. After the operator creates the first consumer commit, `--consumer PATH` hands it to
normal bootstrap. The generated repository owns its files and Git history. Copier is not a runtime dependency, and Maison
does not save or manage an alternate configuration root.

## User-Facing Behavior

Bootstrap setup:

```bash
./bootstrap.sh --setup "$HOME/src/terroir" --host "$(hostname -s)"
```

Manual setup from a Maison checkout:

```bash
mise install uv
MAISON_HOME="$PWD" MAISON_CONSUMER_ROOT="$HOME/src/terroir" \
  mise exec --locked uv -- uvx --from copier copier copy --trust \
    --data "username=$(id -un)" overlay_template "$HOME/src/terroir"
```

The generated `flake.lock` is pinned during bootstrap. Review the generated files and create the consumer's first Git
commit before applying it. `copier update --trust` updates the starter files but does not rerun host registration.

## Design Integration

The feature keeps Maison's ownership boundary intact: Maison owns the framework, schema, bootstrap orchestration, and
mutation task; the generated consumer owns its flake, lock, inventory, user configuration, and Git history. Inventory
mutation continues through `mise run host:add`, preserving repository locks, validation, supported-system checks, and
rollback behavior. Copier is installed ephemerally through Maison-managed `uv` and is not used by runtime commands.

## Operational Impact

Fresh setup needs network access for `uvx copier`, Nix input locking, and normal Git credentials. The generated
repository is initialized as a Git authoring checkout; reviewing and creating its first commit, then publishing a remote,
remain user decisions. A user who declines interactive setup can rerun bootstrap later with `--setup`.

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
- `overlay_template/README.md`
- `overlay_template/dotfiles/README.md`
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
