# Design — MAISON-001: Root-owned deployment transaction state

## Metadata

- Beads feature root: `maison-mol-6y0`
- Feature slug: `maison-001-root-owned-deployment-transactions`
- Design path: `docs/src/features/maison-001-root-owned-deployment-transactions/design.md`
- Implemented record: `docs/src/features/maison-001-root-owned-deployment-transactions/index.md`
- Base branch: `dev`
- Status: delivered
- Review priority: `P0`

## Feature Summary

Move remote repository transaction journals, staging repositories, and rollback repositories out of the managed user's control and into a root-owned same-filesystem transaction area.

## User Intent

The review found that privileged deployment state and rollback data are stored beneath a directory controlled by the managed user. A managed-user compromise can unlink, replace, or interfere with transaction state while privileged finalization is occurring.

## Goals

- Root owns deployment transaction state and journals.
- Staging, rollback, and journal paths live on the same filesystem as the destination.
- Filesystem operations reject symlinks, unexpected ownership, traversal, and cross-device replacement.
- Transactions use unpredictable IDs and a lock that serializes remote repository finalization.

## Non-Goals

- Changing deploy-rs system profile rollback behavior.
- Changing the private overlay split beyond documentation of path ownership.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- Create a root-owned transaction directory outside `/home/<managed-user>` or any managed-user-writable ancestor while remaining on the destination filesystem.
- Use unpredictable transaction IDs, explicit journals, and a single remote transaction lock.
- Validate ownership and permissions of every transaction, staging, rollback, and destination path before mutation.
- Use no-follow filesystem operations for all privileged boundary checks.

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

Replace `<repo>.next.<pid>`, `<repo>.previous`, and `<repo>.deploy-state` with a root-owned transaction manager implemented in tested Python stdlib code. Mise task files may invoke that Python task implementation directly.

The transaction manager uses a root-owned transaction root on the same filesystem as the destination repository. For the default `/home/<managed-user>/.maison` repository path, the default transaction root is a root-owned sibling namespace under `/home`, not under `/home/<managed-user>`, for example `/home/.maison-deploy/transactions/<managed-user>/<repo-hash>/`. If no same-filesystem transaction root exists outside a managed-user-writable ancestor, deployment fails with an actionable error rather than falling back to managed-user-controlled state. A later private overlay may configure an equivalent root-owned transaction root, but the configured path must pass the same same-filesystem, ownership, permission, and no-follow validation.

Each transaction allocates an unpredictable ID beneath that transaction root, creates staging and rollback directories there, writes an explicit journal before each irreversible step, and validates path ownership with directory-file-descriptor based no-follow checks where available. The command surface is limited to stage, finalize, abort, and inspect-incomplete. Revision-bound startup recovery and non-destructive rollback semantics are owned by MAISON-002; this feature only establishes the root-owned state boundary and journal foundation.

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

| Exact page                                                                 | Create or update        | Planned change                                                                                               | Owning Beads task                            |
|----------------------------------------------------------------------------|-------------------------|--------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| README.md                                                                  | Update                  | Replace managed-user-controlled transaction path claims with the root-owned transaction-root contract        | `transaction-contract`, `transaction-engine` |
| docs/deployment.md                                                         | Update                  | Document transaction-root placement, validation, journals, locks, staging, and finalization command behavior | `transaction-contract`, `transaction-engine` |
| docs/recovery.md                                                           | Update                  | Document how to inspect incomplete root-owned transaction journals and where rollback state lives            | `transaction-contract`, `transaction-engine` |
| docs/architecture.md                                                       | Update                  | Record the privileged repository transaction boundary and ownership invariant                                | `transaction-contract`                       |
| docs/task-reference.md                                                     | Update                  | Summarize the deploy task's root-owned repository transaction behavior                                       | `transaction-engine`                         |
| `docs/src/features/maison-001-root-owned-deployment-transactions/index.md` | Create during close-out | Preserve delivery and audit history                                                                          | Close-out documentation                      |
| `docs/src/planned-features.md`                                             | Update                  | Track roadmap status and Beads root                                                                          | Planning                                     |
| `docs/src/SUMMARY.md`                                                      | Update                  | Register this design and delivered record links                                                              | Planning / close-out                         |

## Validation Strategy

- Focused fault-injection tests for managed-user tampering with staging, journal, lock, and rollback paths.
- Behavioral deployment transaction tests covering ownership, no-follow rejection, same-filesystem enforcement, and journal writes.
- `mise -E dev run check` after implementation stabilizes.
- `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-001-root-owned-deployment-transactions transaction-contract` — Add root-owned transaction contract, documentation contract, and tamper tests. This task owns the failing tests and reader-facing contract for transaction-root placement, same-filesystem enforcement, no-follow rejection, ownership validation, journals, and locks.
- `maison-001-root-owned-deployment-transactions transaction-engine` — Implement root-owned transaction staging and journals after the contract task. This task owns the production implementation and updates task-reference/deployment details that depend on the implemented command surface.

## Dependencies and Parallelism

This feature follows the Maison review order. Its implementation tasks depend on specification reconciliation. The
`transaction-engine` task depends on `transaction-contract` so tests and documentation contract land before production
implementation. No implementation task may run until `spec-reconcile` closes.

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
