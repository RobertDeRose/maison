# MAISON-003: Restricted deployment privilege model

## Delivery Summary

- Beads feature root: `maison-mol-4v3`
- Status: delivered
- Pull request: not used for merge-mode delivery
- Merge commit: fast-forward delivery; final target SHA is recorded in the Beads delivery record
- Design record: [design.md](design.md)

## Delivered Capability

Remote Linux deployment now uses a dedicated deployment identity by default instead of direct root deployment or the
managed user account. The default deployment account is `maison-deploy`; the managed user still owns the remote Maison
repository and runs user convergence.

The Linux system-manager module now creates the deployment account and grants only command-scoped passwordless sudo for
reviewed deployment entrypoints:

- preparing the canonical system-manager profile directory,
- running Maison transaction helper `recover`, `stage`, and `finalize` operations,
- and activating the deploy-rs selected system-manager profile.

The previous supported default of broad managed-user `NOPASSWD: ALL` has been removed.

## User-Facing Behavior

Operators keep using the existing command surface:

- `maison deploy <host>`
- `maison deploy <host> --system-only`
- `maison deploy <host> --force-dotfiles`
- `maison system deploy <host>`

Inventory defaults and examples now select `deploy.ssh_user = "maison-deploy"`. Validation rejects configurations where
`deploy.ssh_user` matches the managed username, while `deploy.user_ssh_user` must still match that managed username.
Repository transaction and rollback behavior from MAISON-001 and MAISON-002 remains unchanged.

## Design Integration

MAISON-003 preserves the established two-layer architecture: Nix/Lix owns privileged system state and mise owns user
state. The deployment account is a narrow privileged bridge for remote system activation and root-owned repository
transaction helpers; it is not the managed user and does not own the user environment.

Deploy-rs still selects and verifies the system-manager profile. Maison still stages the repository through the
root-owned same-filesystem transaction namespace before running user convergence as the managed user.

## Operational Impact

Operators must ensure the deployment SSH account can authenticate to deploy-enabled Linux hosts. System-manager manages
the account and sudoers policy after the host has enough initial access to apply the system layer.

Recovery procedures still inspect the root-owned transaction namespace under
`/home/.maison-deploy/transactions/<user>/<repo-hash>/`. Privileged helper recovery runs through the deployment account
with command-scoped sudo instead of through a broadly privileged managed user.

## Reference and Contracts

- [Architecture](../../architecture.md)
- [Remote deployment](../../deployment.md)
- [Recovery](../../recovery.md)
- [Task reference](../../task-reference.md)
- [Adding a Host](../../add-a-host.md)

## Validation Evidence

- `python3 .mise/lib/inventory.py --file inventory.toml validate` — passed.
- `python3 -m py_compile .mise/lib/inventory.py tests/test_topology.py scripts/maison_deploy_transaction.py` — passed.
- `python3 -m unittest -v tests.test_topology.InventoryBehaviorTest tests.test_topology.DeploymentContractTest` — passed.
- `uv run scripts/check-docs.py` — passed.
- `hk fix` and `hk check` — passed for the shellcheck/shebang housekeeping fix that unblocked hook validation.

## Design Reconciliation

### Delivered as Designed

- `maison-deploy` is the default deployment SSH user in Python and Nix inventory paths.
- Deployment and managed user identities are validated separately.
- Remote deployment helper calls and profile preparation use command-scoped sudo when the deployment account is not root.
- Linux sudoers no longer grants the managed user `NOPASSWD: ALL` by default.
- Reader-facing deployment, recovery, architecture, add-host, and task-reference pages describe the new account boundary.

### Intentional Changes

- The sudoers account name comes from the validated deploy inventory user (`host.deploy.sshUser`), whose default is
  `maison-deploy`, rather than being hard-coded in the Linux module. This keeps explicit non-managed deployment account
  overrides aligned with the same restricted privilege contract.

### Deferred Work

- Private overlay-managed authorized-key material remains part of the later private overlay feature; public Maison still
  avoids embedding site-specific trusted access material.

### Rejected or Removed Scope

- Broad `NOPASSWD: ALL` for the managed Linux user is no longer supported as the default Maison deployment model.
- Direct root deployment remains possible only when explicitly configured; it is no longer the default path.

## Documentation Updated

- `docs/add-a-host.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/recovery.md`
- `docs/task-reference.md`
- `docs/src/features/maison-003-restricted-deployment-privilege/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation task: `maison-mol-9mi`.
- Implementation coordinator: `maison-mol-u8y`.
- Contract-test implementation task: `maison-mol-u8y.1`, commit `09e4fdfd2b027db782d04eb7a10a20178b272c30`.
- Restricted privilege implementation task: `maison-mol-u8y.2`, commit `26a8411b1964b0a54103c6a7fa06584696698d61`.
- Shellcheck housekeeping commit: `e322902c674c59069cc071d4166de17af7e0d5708`.
- Validation task: `maison-mol-safe`.
