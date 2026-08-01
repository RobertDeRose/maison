# MAISON-015: Linux runtime activation verification

## Delivery Summary

- Beads feature root: `maison-mol-cg3x`
- Status: delivered
- Pull request: not created (direct fast-forward merge)
- Merge commit: `410d571182fba2c9835f2f33f08bee351cb73ac0` (fast-forward into `dev`)
- Design record: [design.md](design.md)

## Delivered Capability

Maison now verifies the active Linux runtime as part of system-manager activation instead of assuming that generated
configuration files alone changed the running host. The supported Linux runtime is systemd-backed and failures are
reported as actionable activation errors.

## User-Facing Behavior

Operators continue using the existing `maison` and mise command surfaces. Linux activation now:

- requires a running systemd runtime and working `systemctl`;
- verifies `hostname --static` against the inventory host name;
- manages and verifies the `America/New_York` timezone through systemd runtime state and `/etc/localtime`;
- validates SSH configuration with `sshd -t` and reloads or restarts the active `ssh.service` or `sshd.service`;
- fails when SSH validation or reload fails rather than suppressing the error; and
- verifies that `system-manager.target` and `prefill-authorized-keys.service` are active.

The same system-manager activation path is used for local activation and deploy-rs remote activation. No non-systemd
fallback or parallel deployment verification path was added.

## Design Integration

The implementation keeps Nix/Lix as the privileged system layer and mise as the user convergence layer. Native
system-manager configuration manages the hostname, timezone files, SSH service, and required service units. A small
Python standard-library verifier provides field-specific runtime diagnostics, while the existing authorized-key
prefill service owns SSH configuration validation and reload failure propagation.

The ownership boundary, supported platforms, absence of Home Manager, public-safe inventory model, and existing
operator command surface remain unchanged.

## Operational Impact

Linux hosts must run systemd as the active init system. A missing systemd runtime, hostname or timezone mismatch,
invalid SSH configuration, failed SSH reload, or inactive required unit stops activation before user convergence can
continue. Operators should use the reported runtime field to correct the host or configuration and retry the existing
activation command.

See [deployment](../../deployment.md) for system activation, [operations](../../operations.md) for the command
workflow, and [recovery](../../recovery.md) for failed activation behavior.

## Reference and Contracts

- [Architecture](../../architecture.md)
- [Remote deployment](../../deployment.md)
- [Operations](../../operations.md)
- [Recovery](../../recovery.md)
- [Feature design](design.md)

## Validation Evidence

- `python3 -m unittest -v tests.test_linux_runtime_verification tests.test_deployment_contracts tests.test_ownership_boundary` — passed (48 tests).
- Runtime helper smoke checks with fake `systemctl`, `hostname`, `timedatectl`, `readlink`, and `sshd` commands — passed for matching state and hostname mismatch failure.
- `python3 -m py_compile scripts/verify_linux_runtime.py tests/test_linux_runtime_verification.py` — passed.
- `shellcheck -x .mise/tasks/system/apply` and `nixfmt --check nix/modules/linux/system.nix nix/lib/deployments.nix` — passed.
- `uv run scripts/check-docs.py` — passed after close-out reconciliation.
- `mise exec -- hk check` — passed.
- `mise -E dev run check` — passed (152 tests plus data, shell, and Nix checks).

## Design Reconciliation

### Delivered as Designed

- Added a systemd-only pre-activation assertion with an actionable failure when systemd or `systemctl` is unavailable.
- Managed `/etc/localtime` from the pinned timezone data while retaining the compatibility `/etc/timezone` file.
- Added post-activation verification for hostname, timezone, localtime, required service units, and SSH state.
- Made `sshd -t` and active SSH reload failures fail activation without suppression.
- Reused the same system-manager activation path for local and deploy-rs activation, with explicit degraded-target
  rejection in both adapters.
- Added behavioral tests for matching state, missing systemd, hostname/timezone/localtime mismatch, SSH failures,
  inactive units, persistent service state, pre-existing localtime, and activation adapter failure handling.

### Intentional Changes

- The reviewed design's systemd-only decision was recorded explicitly during feature activation; non-systemd fallback
  remains unsupported rather than receiving a compatibility path.
- Runtime diagnostics live in `scripts/verify_linux_runtime.py` and are embedded into the system-manager closure as a
  small Python standard-library helper, keeping stateful behavior testable without adding a separate deployment path.
- Local and deploy-rs adapters explicitly verify the target and runtime verifier service after system-manager returns,
  because the pinned system-manager engine reports service-job failures through activation output.

### Deferred Work

- Pull-request and merge metadata remain pending the delivery action selected after close-out.
- Actual systemd-host integration testing is not available in the repository validation environment; contract tests and
  command smoke checks cover the implemented failure boundaries.

### Rejected or Removed Scope

- No non-systemd Linux fallback was added.
- No parallel deploy-rs verifier or alternate activation pipeline was introduced.
- No Home Manager, package ownership, user convergence, or supported-platform boundary changes were made.

## Documentation Updated

- `docs/architecture.md`
- `docs/deployment.md`
- `docs/operations.md`
- `docs/recovery.md`
- `docs/src/features/maison-015-linux-runtime-verification/design.md`
- `docs/src/features/maison-015-linux-runtime-verification/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation and reviewed design: `maison-mol-08vr`, commit `ca36568866916f0e1f96170ea97a75bf46f365e6`.
- Runtime contract tests: `maison-mol-ln6g.1`, commit `f4e384adc165381aba24b3554254545bbd63f511`.
- Runtime implementation: `maison-mol-ln6g.2`, commit `88532ab9ed9024d251ea361a9282502eecb8f787`.
- Close-out reconciliation, activation-gating fixes, and navigation: commit `6701bb8ad1bd3a32b47c849e773551c09d16f81f`.
- Documentation reconciliation: `maison-mol-176d`.
- Validation: `maison-mol-xq97`.
- Holistic delivery review: `maison-mol-9n4b`.
- Documentation drift review: `maison-mol-1hla`.
- Delivery action: `maison-mol-miwi`, fast-forward merge into `dev` at `410d571182fba2c9835f2f33f08bee351cb73ac0`.
