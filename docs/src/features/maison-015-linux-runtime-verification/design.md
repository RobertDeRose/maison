# Design — MAISON-015: Linux runtime activation verification

## Metadata

- Beads feature root: `maison-mol-cg3x`
- Feature slug: `maison-015-linux-runtime-verification`
- Design path: `docs/src/features/maison-015-linux-runtime-verification/design.md`
- Implemented record: `docs/src/features/maison-015-linux-runtime-verification/index.md`
- Base branch: `dev`
- Status: draft
- Review priority: `P1`

## Feature Summary

Verify Linux runtime state after activation rather than only writing configuration files.

## User Intent

Writing `/etc/hostname` does not necessarily update the active hostname; writing `/etc/timezone` does not establish `/etc/localtime`; SSH reload failures are suppressed.

## Goals

- Post-activation checks verify active hostname, timezone, SSH configuration, and service unit state.
- Native system-manager options are used where possible.
- SSH reload failures are surfaced.

## Non-Goals

- Replacing system-manager activation as the Linux system layer.
- Supporting Linux hosts without systemd; MAISON-015 supports systemd-backed Linux hosts only.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- Linux activation requires systemd as the running init system and fails with an actionable diagnostic when systemd or
  `systemctl` is unavailable; no non-systemd fallback is supported.
- Use system-manager/native mechanisms for hostname, timezone, SSH config, and services where available.
- After activation, verify that `hostname --static` equals the configured host name and that the active timezone is
  `America/New_York` through systemd's runtime state and `/etc/localtime`.
- Validate the active SSH configuration with `sshd -t`, reload or restart the active `ssh.service` or `sshd.service`,
  and fail activation when the check or reload fails; no SSH reload failure may be suppressed.
- Verify that `system-manager.target` and the Maison-managed `prefill-authorized-keys.service` reach an active state.
- Activation fails or reports a clear degraded state when runtime checks do not match intended configuration.
- Tests cover active hostname, `/etc/localtime`, SSH reload failure, and active service unit verification.

### Quality Requirements

- Preserve Maison's Nix/Lix system ownership and mise user ownership boundary.
- Prefer tested Python stdlib implementations for stateful behavior. Python task files under `.mise/tasks/` are
  acceptable, including `usage` comments for argument validation and mise templating or sandboxing where useful.
- Do not introduce a Rust helper unless a later design proves Python cannot safely satisfy the filesystem or privilege
  boundary.
- Keep implementation small, reviewable, and covered by behavioral or fault-injection tests before relying on it.

### Compatibility and Migration Requirements

- Preserve supported platforms: `aarch64-darwin`, `aarch64-linux`, and `x86_64-linux`.
- Preserve the absence of Home Manager.
- Update existing commands in place rather than introducing parallel legacy paths.
- Public Maison remains generic and public-safe; personal/site configuration belongs in a private overlay where relevant.

## Existing Context

Maison currently documents a two-layer architecture where Nix/Lix owns privileged system state and mise owns user state.
The review of commit `ded7bbb745f34f1059930fc48eadafe267399ab2` identified this feature as required work. Existing
reader documentation under `docs/` describes the target operations and must be reconciled with delivered behavior.

## Proposed Design

Extend `nix/modules/linux/system.nix` with one systemd-backed activation verification path. A pre-activation assertion
requires a running systemd instance and `systemctl`; a host without that runtime fails before Maison replaces system
files. Use system-manager's Nix module mechanisms for the managed service units, source the managed timezone data into
`/etc/localtime` while retaining the compatibility `/etc/timezone` file, and keep hostname configuration tied to the
inventory host name.

The existing `prefill-authorized-keys.service` validates `sshd -t` and reloads or restarts the active SSH unit without
suppressing failure. A dependent `maison-runtime-verification.service` runs after that service and verifies the active
static hostname, systemd-reported timezone, `/etc/localtime`, `system-manager.target`, and
`prefill-authorized-keys.service`. It exits non-zero with a field-specific diagnostic for any mismatch. The same
system-manager activation service is used by local activation and deploy-rs remote activation; no separate deployment
or non-systemd verification pipeline is introduced.

## Architecture Consistency

### Existing Patterns Reused

- Nix/Lix remains the privileged system layer.
- mise remains the user command and package/dotfile layer.
- `maison check` remains the repository-wide validation entrypoint.
- Python is the preferred home for stateful behavior that needs tests, parsing, locks, manifests, or recovery.

### Invariants Preserved

- A file, package, service, or preference has exactly one owner.
- Intel macOS remains unsupported.
- Remote deployment remains split between deploy-rs system-profile handling and Maison repository/user handling.
- Public Maison does not contain private infrastructure identity or trusted access material.

### New Decisions Introduced

- This feature adopts the concrete behavior described in **Proposed Design** as the supported Maison contract.

### Architecture Documentation Changes

Update the architecture and operations pages named in **Documentation Impact** so current reader-facing docs match the
implemented behavior.

## Operational Considerations

Operators should receive explicit errors, recovery instructions, and validation evidence for this feature's failure
modes. Recovery docs must distinguish Nix generation behavior, repository/source behavior, user convergence behavior,
and external package-manager side effects when those concerns apply.

## Documentation Impact

| Exact page                                                         | Create or update        | Planned change                                                                      | Owning Beads task       |
|--------------------------------------------------------------------|-------------------------|-------------------------------------------------------------------------------------|-------------------------|
| docs/architecture.md                                               | Update                  | Align reader-facing contract with MAISON-015: Linux runtime activation verification | Implementation tasks    |
| docs/operations.md                                                 | Update                  | Align reader-facing contract with MAISON-015: Linux runtime activation verification | Implementation tasks    |
| docs/recovery.md                                                   | Update                  | Align reader-facing contract with MAISON-015: Linux runtime activation verification | Implementation tasks    |
| docs/deployment.md                                                 | Update                  | Align reader-facing contract with MAISON-015: Linux runtime activation verification | Implementation tasks    |
| `docs/src/features/maison-015-linux-runtime-verification/index.md` | Create during close-out | Preserve delivery and audit history                                                 | Close-out documentation |
| `docs/src/planned-features.md`                                     | Update                  | Track roadmap status and Beads root                                                 | Planning                |
| `docs/src/SUMMARY.md`                                              | Update                  | Register this design and delivered record links                                     | Planning / close-out    |

## Validation Strategy

- Nix/system-manager checks for generated activation verification and systemd-only assertions.
- Behavioral tests simulating hostname/timezone/SSH/service mismatch, missing systemd, and reload failure.
- `mise -E dev run check` and `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-015-linux-runtime-verification runtime-contract` — Add Linux runtime verification tests.
- `maison-015-linux-runtime-verification runtime-implementation` — Implement Linux post-activation runtime checks.

## Dependencies and Parallelism

This feature follows the Maison review order. Its implementation tasks depend on specification reconciliation. Sibling
implementation tasks may run in parallel only when they do not edit the same command path, test file, or documentation
page.

## Rollout and Migration

Roll out by updating tests and docs first, then replacing the existing implementation path. Existing commands keep their
names unless a feature explicitly narrows unsafe behavior.

## Risks and Tradeoffs

- Safety fixes may temporarily reduce permissive behavior that previously appeared to work.
- Deployment and recovery changes require fault-injection coverage because ordinary happy-path tests are insufficient.
- Keeping shell and mise task compatibility while moving logic into Python may require small adapter changes.

## Rejected Alternatives

- Broad rewrite before fixing the review findings.
- Preserving unsafe legacy paths as supported behavior.
- Storing private infrastructure identity in public Maison defaults.

## Open Questions

None.

## Deferred Decisions

None.

## Planning Record

### Questions Asked and Answers

- Stateful Maison behavior should move into tested Python implementations. `.mise/tasks/` may contain Python task files
  and may use `usage` comments, task templating, and sandboxing.
- The default privileged deployment account is `maison-deploy`.
- Maison is the reusable vehicle; a tracked private overlay repository is the driver for personal/site configuration.
- Fresh setup supports `--overlay <git-url-or-path>`, prompts only when interactive, and fails clearly when a required
  overlay is missing in non-interactive mode.
- Public examples should be real workable starter configurations without personal infrastructure identity.

### Assumptions

- The reviewed commit and review summary are authoritative planning evidence for this remediation roadmap.
- Feature branches should base on `dev`.

### Design Changes During Planning

- The private inventory model changed from untracked local TOML to a tracked private overlay repository to preserve
  Maison's durability and replication goals.

### Source Material

- Maison review summary for commit `ded7bbb745f34f1059930fc48eadafe267399ab2`.
- Current Maison documentation under `README.md` and `docs/`.
