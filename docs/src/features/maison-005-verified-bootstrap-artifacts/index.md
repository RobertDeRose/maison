# MAISON-005: Verified bootstrap artifacts

## Delivery Summary

- Beads feature root: `maison-mol-pa6`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison bootstrap no longer executes downloaded installer content before verification. Local bootstrap, shared Lix setup,
and the remote deployment mise fallback now download Maison-owned artifacts to disk, verify checked-in SHA-256 metadata,
and install or execute only verified local files.

A checked-in manifest at `bootstrap/artifacts.toml` is the public trust root for supported mise and Lix bootstrap
artifacts on `aarch64-darwin`, `aarch64-linux`, and `x86_64-linux`. Maison runtime inputs required during bootstrap and
command execution are pinned to immutable versions or revisions.

## User-Facing Behavior

Operators keep the existing command surface. Fresh setup uses a reviewed local checkout or a downloaded bootstrap file
that is verified before execution. When mise or Lix is missing, Maison installs the pinned artifact for the current
supported system. Verification failure stops bootstrap with an actionable error rather than continuing with untrusted
content.

Remote Linux deployment preserves the existing system/user split. If the managed user lacks mise during repository/user
convergence, the staged repository provides the same verified mise install fallback.

## Design Integration

The implementation preserves Maison's architecture boundaries: Nix/Lix remains the privileged system layer and mise
remains the user command, package, and dotfile layer. Verification logic is centralized in shared bootstrap shell helpers
for task compatibility, with a tested Python verifier for manifest/checksum behavior.

The immutable-input guardrails target Maison bootstrap/runtime inputs only. Ordinary non-bootstrap workstation tools may
still use the repository's existing `latest` policy when generated lockfiles capture resolved artifacts.

## Operational Impact

Operators can inspect or update reviewed bootstrap metadata in `bootstrap/artifacts.toml`. A checksum mismatch indicates
that the downloaded artifact differs from the reviewed trust root; recovery is to retry once for partial downloads, then
review the upstream release before changing the manifest or manually installing the same verified artifact.

## Reference and Contracts

- [Operations](../../operations.md)
- [Remote deployment](../../deployment.md)
- [Recovery](../../recovery.md)
- [Task reference](../../task-reference.md)

## Validation Evidence

- `python3 -m py_compile tests/test_topology.py scripts/verify_bootstrap_artifact.py` — passed.
- `python3 -m unittest -v tests.test_topology.VerifiedBootstrapContractTest tests.test_topology.OwnershipBoundaryTest.test_repository_tools_are_isolated_from_machine_convergence` — passed.
- `uv run scripts/check-docs.py` — passed.
- `shellcheck -x bootstrap.sh .mise/lib/bootstrap.sh .mise/tasks/deploy` — passed.
- `mise -E dev run check` — passed.

## Design Reconciliation

### Delivered as Designed

- Local bootstrap no longer recommends or performs pipe-to-shell installer execution.
- Shared Lix setup downloads a pinned installer artifact, verifies its SHA-256 digest, then executes the local file.
- Remote deployment's mise fallback installs a verified pinned mise binary from the staged repository metadata.
- Public bootstrap examples avoid pipe-to-shell instructions.
- Source-text guard tests reject unsafe bootstrap patterns and mutable Maison runtime/plugin references.
- Manifest and verifier tests cover required metadata, supported-system selection, checksum success, and checksum
  mismatch failure.

### Intentional Changes

- The checked-in manifest uses per-platform metadata under each artifact so supported systems can use platform-specific
  URLs and checksums while sharing version and recovery fields.
- The existing `usage` Maison runtime tool is pinned to `4.0.0`; the broader user-tool latest policy remains documented
  and tested for non-bootstrap tools.

### Deferred Work

None.

### Rejected or Removed Scope

- Unverified `curl ... | sh` and `curl ... | bash` paths were removed from Maison-owned bootstrap surfaces.
- Private overlay artifact metadata was not introduced as the public default trust root; it remains reserved for future
  site-specific mirrors or overrides.

## Documentation Updated

- `README.md`
- `docs/deployment.md`
- `docs/operations.md`
- `docs/recovery.md`
- `docs/task-reference.md`
- `docs/src/features/maison-005-verified-bootstrap-artifacts/design.md`
- `docs/src/features/maison-005-verified-bootstrap-artifacts/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation task: `maison-mol-0od`, commit `63aa235`.
- Implementation coordinator: `maison-mol-b2j`.
- Bootstrap contract task: `maison-mol-b2j.1`, commit `da8eb56`.
- Bootstrap implementation task: `maison-mol-b2j.2`, commit `2a93428`.
- Documentation reconciliation task: `maison-mol-46k`.
- Validation task: `maison-mol-bx6`.
