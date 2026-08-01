# Design — MAISON-002: Revision-bound commit and rollback

## Metadata

- Beads feature root: `maison-mol-quq`
- Feature slug: `maison-002-revision-bound-commit-rollback`
- Design path: `docs/src/features/maison-002-revision-bound-commit-rollback/design.md`
- Implemented record: `docs/src/features/maison-002-revision-bound-commit-rollback/index.md`
- Base branch: `dev`
- Status: draft
- Review priority: `P0`

## Feature Summary

Make remote repository commit and rollback revision-bound, recoverable, non-destructive, and startup-recoverable.

## User Intent

The rollback implementation can remove the active repository before proving that restoration will succeed. Finalization also lacks expected old/new revision checks.

## Goals

- Record and verify expected old and new Maison revisions.
- Never delete the active repository before a recoverable replacement exists.
- Provide rescue renames, filesystem synchronization, and startup recovery.
- Fault-injection tests cover interruption at every finalization step.

## Non-Goals

- Changing package-manager rollback semantics.
- Replacing deploy-rs rollback.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- Journal expected old revision, candidate new revision, destination path, and recovery action before finalization.
- Verify active old revision before replacement and active new revision after replacement.
- Preserve at least one recoverable prior repository until success is proven and synchronized.
- Recover or stop safely when a previous transaction journal is found at startup.

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

Extend the transaction manager from MAISON-001 with revision-bound state transitions. Finalization validates the active old revision, validates the staged new revision, performs atomic rescue renames without deleting the active repository first, fsyncs parent directories and journal updates where supported, then records completion. Startup recovery reads incomplete journals and either completes a proven-safe transition or restores the previous repository before user convergence runs.

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

| Exact page                                                             | Create or update        | Planned change                                                                   | Owning Beads task       |
|------------------------------------------------------------------------|-------------------------|----------------------------------------------------------------------------------|-------------------------|
| docs/deployment.md                                                     | Update                  | Align reader-facing contract with MAISON-002: Revision-bound commit and rollback | Implementation tasks    |
| docs/recovery.md                                                       | Update                  | Align reader-facing contract with MAISON-002: Revision-bound commit and rollback | Implementation tasks    |
| docs/operations.md                                                     | Update                  | Align reader-facing contract with MAISON-002: Revision-bound commit and rollback | Implementation tasks    |
| docs/task-reference.md                                                 | Update                  | Align reader-facing contract with MAISON-002: Revision-bound commit and rollback | Implementation tasks    |
| `docs/src/features/maison-002-revision-bound-commit-rollback/index.md` | Create during close-out | Preserve delivery and audit history                                              | Close-out documentation |
| `docs/src/planned-features.md`                                         | Update                  | Track roadmap status and Beads root                                              | Planning                |
| `docs/src/SUMMARY.md`                                                  | Update                  | Register this design and delivered record links                                  | Planning / close-out    |

## Validation Strategy

- Fault-injection tests for interruption before, during, and after active repository replacement.
- Tests for old-revision mismatch, new-revision mismatch, missing staged repository, missing previous repository, and startup recovery.
- `mise -E dev run check` and `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-002-revision-bound-commit-rollback revision-contract` — Add revision-bound finalization and recovery tests.
- `maison-002-revision-bound-commit-rollback revision-engine` — Implement non-destructive revision-bound finalization.

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
