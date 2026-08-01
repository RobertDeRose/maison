# Design — MAISON-013: Exact dotfile backup manifests

## Metadata

- Beads feature root: `maison-mol-h8e`
- Feature slug: `maison-013-dotfile-backup-manifests`
- Design path: `docs/src/features/maison-013-dotfile-backup-manifests/design.md`
- Implemented record: `docs/src/features/maison-013-dotfile-backup-manifests/index.md`
- Base branch: `dev`
- Status: draft
- Review priority: `P1`

## Feature Summary

Preserve exact filesystem objects in dotfile backups with structured manifests and full restoration tests.

## User Intent

`cp -RLp` dereferences symlinks and can copy content from outside the managed path.

## Goals

- Backups preserve whether each original object was a file, directory, or symlink.
- Symlink backups record exact symlink targets without dereferencing.
- Structured manifests drive restoration and audit.
- Restoration tests cover files, directories, symlinks, and failures.

## Non-Goals

- Backing up arbitrary unmanaged directories outside refused dotfile targets.
- Replacing application bundle backup archives covered by separate app backup logic.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- Replace dereferencing copy behavior for dotfile conflicts.
- Write a manifest containing source path, object type, mode, timestamps where supported, symlink target, backup path, and restore status.
- Refuse or safely handle unsupported special files.
- Docs explain backup inspection and restoration.

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

Implement dotfile backups through one Python-stdlib manifest module, called by the existing forced-handoff shell adapter. Each backup directory contains an atomically written `manifest.json` with a version, home-relative source path, object type, mode, supported timestamps, backup-relative payload path, symlink target where applicable, and per-entry restore status. The module snapshots objects using `lstat`: regular files and directories retain metadata, symlinks are recreated by their target string without traversal, and socket, FIFO, block, and character objects fail before any source is removed.

Expose restoration as `maison user restore-dotfiles <backup-directory> --force`. It accepts only a backup directory below `$HOME/.local/state/maison/backups/dotfiles`, validates every manifest path and payload containment before changing targets, and requires `--force` to replace an existing target. It restores only manifest-recorded pending entries; after each successful entry it atomically records `restored` status. A failed entry stops the operation and leaves prior statuses durable for a safe retry.

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

- This feature adopts the concrete behavior described in **Proposed Design** as the supported Maison contract: manifest data is authoritative for restore and audit; backup preserves `lstat` object identity and never traverses a refused-target symlink.

### Architecture Documentation Changes

Update the architecture and operations pages named in **Documentation Impact** so current reader-facing docs match the
implemented behavior.

## Operational Considerations

Operators should receive explicit errors, recovery instructions, and validation evidence for this feature's failure
modes. Recovery docs must distinguish Nix generation behavior, repository/source behavior, user convergence behavior,
and external package-manager side effects when those concerns apply.

## Documentation Impact

| Exact page                                                       | Create or update        | Planned change                                                               | Owning Beads task       |
|------------------------------------------------------------------|-------------------------|------------------------------------------------------------------------------|-------------------------|
| docs/recovery.md                                                 | Update                  | Align reader-facing contract with MAISON-013: Exact dotfile backup manifests | Implementation tasks    |
| docs/operations.md                                               | Update                  | Align reader-facing contract with MAISON-013: Exact dotfile backup manifests | Implementation tasks    |
| docs/task-reference.md                                           | Update                  | Align reader-facing contract with MAISON-013: Exact dotfile backup manifests | Implementation tasks    |
| `docs/src/features/maison-013-dotfile-backup-manifests/index.md` | Create during close-out | Preserve delivery and audit history                                          | Close-out documentation |
| `docs/src/planned-features.md`                                   | Update                  | Track roadmap status and Beads root                                          | Planning                |
| `docs/src/SUMMARY.md`                                            | Update                  | Register this design and delivered record links                              | Planning / close-out    |

## Validation Strategy

- Backup/restore tests for regular files, directories, symlinks, missing targets, malformed manifests, and unsupported objects.
- Tests proving external symlink targets are not copied into backups and restore cannot traverse outside `$HOME` or the supplied backup directory.
- Tests proving restore requires `--force`, preserves pending/restored manifest status across a partial failure, and replaces only manifest-recorded targets.
- `mise -E dev run check` and `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-013-dotfile-backup-manifests backup-contract` — Add failing tests for manifest schema, exact backup/restore identity, rejected paths/types, force requirement, and partial restore status.
- `maison-013-dotfile-backup-manifests backup-implementation` — Implement the stdlib manifest module, existing handoff adapter, restore task, reader docs, and contract tests.

## Dependencies and Parallelism

This feature follows the Maison review order. Its implementation tasks depend on specification reconciliation.
`backup-contract` precedes `backup-implementation`, because its fixtures and assertions define the manifest and restore
contract. No implementation tasks run in parallel for this feature.

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

- Restoration is exposed as `maison user restore-dotfiles <backup-directory> --force`; the explicit force flag is required for any target replacement.
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
