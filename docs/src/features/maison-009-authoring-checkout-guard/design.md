# Design — MAISON-009: Authoring checkout guard

## Metadata

- Beads feature root: `maison-mol-74l`
- Feature slug: `maison-009-authoring-checkout-guard`
- Design path: `docs/src/features/maison-009-authoring-checkout-guard/design.md`
- Implemented record: `docs/src/features/maison-009-authoring-checkout-guard/index.md`
- Base branch: `dev`
- Status: reviewed
- Review priority: `P1`

## Feature Summary

Prevent authoring commands from modifying deployed snapshots that lack `.git` and will be overwritten by the next deployment.

## User Intent

Remote archives intentionally contain no `.git`, but mutation commands remain exposed. These edits are ephemeral and misleading.

## Goals

- Mutation commands require an authoring checkout for the target repository they write.
- Deployed snapshots reject authoring commands with clear guidance.
- Read-only operational commands remain available in deployed snapshots where safe.

## Non-Goals

- Adding Git to remote deployment archives.
- Blocking user convergence in deployed snapshots.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- All mutating authoring commands verify an authoring checkout before writing the target repository.
- Deployed snapshots are detected by absence of `.git` plus Maison revision metadata.
- A `.git` directory or worktree `.git` file counts as authoring checkout evidence.
- Error messages point to the private overlay or authoring repo workflow.
- Task reference distinguishes authoring-only commands from deployed runtime commands.

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

Add a shared stdlib Python checkout-mode detector beside the existing repository mutation helper. Mutation tasks call it for the target repository before acquiring the mutation lock and before writing. The detector inspects only checkout marker state (`.git` or `.maison-revision`) so it does not read mutable TOML, lockfiles, or journaled content before MAISON-008 startup recovery.

In deployed snapshots, mutators fail with a non-zero status and an explanation that source edits must happen in an authoring checkout or private overlay repository. `host:add` guards the active inventory repository after resolving `inventory_root`, so a deployed public Maison snapshot may still add hosts to a private overlay clone when that overlay clone is a Git checkout. Read-only status, plan, apply, and recovery operations keep their current deployed behavior.

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

| Exact page                                                       | Create or update        | Planned change                                                                         | Owning Beads task       |
|------------------------------------------------------------------|-------------------------|----------------------------------------------------------------------------------------|-------------------------|
| docs/architecture.md                                             | Update                  | Document the authoring checkout versus deployed snapshot boundary                      | Implementation tasks    |
| docs/operations.md                                               | Update                  | Align reader-facing contract with MAISON-009: Authoring checkout guard                 | Implementation tasks    |
| docs/task-reference.md                                           | Update                  | Distinguish authoring-only commands from deployed runtime commands                     | Implementation tasks    |
| docs/deployment.md                                               | Update                  | Explain deployed archives are runtime snapshots, not authoring checkouts               | Implementation tasks    |
| docs/recovery.md                                                 | Update                  | Explain rejected deployed-snapshot authoring commands and overlay/source recovery path | Implementation tasks    |
| `docs/src/features/maison-009-authoring-checkout-guard/index.md` | Create during close-out | Preserve delivery and audit history                                                    | Close-out documentation |
| `docs/src/planned-features.md`                                   | Update                  | Track roadmap status and Beads root                                                    | Planning                |
| `docs/src/SUMMARY.md`                                            | Update                  | Register this design and delivered record links                                        | Planning / close-out    |

## Validation Strategy

- Gitless deployment fixture tests for every authoring mutator.
- Tests proving runtime apply/status commands still work without `.git`.
- `mise -E dev run check` and `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-009-authoring-checkout-guard checkout-contract` — Add deployed-snapshot authoring guard tests.
- `maison-009-authoring-checkout-guard checkout-implementation` — Implement authoring checkout guard after the contract tests are committed.

## Dependencies and Parallelism

This feature follows the Maison review order. Its implementation tasks depend on specification reconciliation. The
checkout implementation depends on the checkout contract task so tests land before behavior changes; these two tasks are
sequential because they cover the same command surface, tests, and documentation pages.

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

### Design Changes During Specification Review

- Narrowed deployed-snapshot behavior to fail-fast rejection instead of dynamic task hiding.
- Clarified that checkout guards apply to the target repository being written, preserving private overlay host authoring.
- Clarified that checkout detection uses only marker state and does not weaken MAISON-008 lock and journal recovery
  ordering.
- Added architecture documentation to the reader-facing documentation impact.

### Source Material

- Maison review summary for commit `ded7bbb745f34f1059930fc48eadafe267399ab2`.
- Current Maison documentation under `README.md` and `docs/`.
