# Design — MAISON-012: Plan/apply semantic parity

## Metadata

- Beads feature root: `maison-mol-6w9`
- Feature slug: `maison-012-plan-apply-parity`
- Design path: `docs/src/features/maison-012-plan-apply-parity/design.md`
- Implemented record: `docs/src/features/maison-012-plan-apply-parity/index.md`
- Base branch: `dev`
- Status: reviewed
- Review priority: `P1`

## Feature Summary

Make `maison user plan` execute the same semantics as `maison user apply`, differing only by dry-run execution.

## User Intent

`user plan` always enables forced dotfile behavior while the default apply path does not.

## Goals

- Plan and apply share one argument-construction path.
- Dry-run is the only semantic difference for a given flag set unless an option explicitly documents otherwise.
- Dotfile force behavior is visible and consistent: plan and apply default to no forced replacement, and
  `--force-dotfiles` is explicit for both preview and apply.

## Non-Goals

- Changing the documented default safety posture for destructive dotfile replacement without tests.
- Changing package-manager dry-run capabilities beyond existing supported flags.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- Centralize user-layer argument construction for plan and apply in a testable Python module or function.
- `maison user plan`, `maison user apply`, aggregate `maison plan`, and aggregate `maison apply` use the same
  force-dotfile flag semantics: default false, explicit `--force-dotfiles` true.
- Tests prove force-dotfile flags, package/app/tool command steps, lock handling, and preference steps are identical for
  plan and apply except dry-run execution and explicitly documented command substitutions.
- Docs accurately describe preview, apply, default dotfile safety, and force-dotfile preview/apply behavior.

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

Move user convergence argument construction into one tested Python module or function. `user plan` and `user apply` call
the same builder with an execution mode and the same parsed user flags. The builder emits a structured command plan used
by tests and both task entrypoints. It preserves the existing command order: prepare dotfiles, apply or preview dotfiles,
link or preview mise lockfiles, run package convergence or its supported dry-run substitute, apply or preview remaining
mise user state, and run finalize only for apply.

Default dotfile force behavior is safe and identical: no forced replacement unless `--force-dotfiles` is supplied.
`user plan --force-dotfiles` previews the same forced dotfile handoff that `user apply --force-dotfiles` performs, but
with dry-run execution. Aggregate `maison plan --force-dotfiles` forwards the same user-layer flag just as aggregate
`maison apply --force-dotfiles` does.

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

- User plan/apply command construction is owned by one structured command-plan builder.
- For the same user flags, plan and apply differ only by dry-run execution and documented command substitutions.
- Forced dotfile replacement remains opt-in for both preview and apply.

### Architecture Documentation Changes

Update the architecture and operations pages named in **Documentation Impact** so current reader-facing docs match the
implemented behavior.

## Operational Considerations

Operators should receive explicit errors, recovery instructions, and validation evidence for this feature's failure
modes. Recovery docs must distinguish Nix generation behavior, repository/source behavior, user convergence behavior,
and external package-manager side effects when those concerns apply.

## Documentation Impact

| Exact page                                                | Create or update        | Planned change                                                                                                                        | Owning Beads task       |
|-----------------------------------------------------------|-------------------------|---------------------------------------------------------------------------------------------------------------------------------------|-------------------------|
| docs/operations.md                                        | Update                  | Document plan/apply parity, default no-force dotfile behavior, and `--force-dotfiles` preview/apply flow                              | Implementation tasks    |
| docs/recovery.md                                          | Update                  | Replace force-enabled dry-run wording with explicit `user plan --force-dotfiles` then `user apply --force-dotfiles` recovery guidance | Implementation tasks    |
| docs/task-reference.md                                    | Update                  | Document `plan`/`user:plan` force-dotfile flag behavior and dry-run-only command differences                                          | Implementation tasks    |
| `docs/src/features/maison-012-plan-apply-parity/index.md` | Create during close-out | Preserve delivery and audit history                                                                                                   | Close-out documentation |
| `docs/src/planned-features.md`                            | Update                  | Track roadmap status and Beads root                                                                                                   | Planning                |
| `docs/src/SUMMARY.md`                                     | Update                  | Register this design and delivered record links                                                                                       | Planning / close-out    |

## Validation Strategy

- Focused tests comparing generated plan/apply structured command plans for default and `--force-dotfiles` modes.
- Behavioral tests for aggregate `plan` and `apply` force-dotfile forwarding.
- Behavioral tests for force-dotfile conflict previews and applies.
- `mise -E dev run check` and `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-012-plan-apply-parity parity-contract` — Add user plan/apply parity tests for structured command plans,
  force-dotfile defaults, explicit force mode, package/tool/app/lock/preference steps, and aggregate flag forwarding.
- `maison-012-plan-apply-parity parity-implementation` — Centralize user convergence argument construction and update
  task entrypoints/docs to use the shared builder.

## Dependencies and Parallelism

This feature follows the Maison review order. Both implementation tasks depend on specification reconciliation. The
parity-implementation task depends on the parity-contract task because the tests define the accepted command-plan and
flag-forwarding behavior. The implementation tasks are sequential.

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

- Clarified that plan/apply parity applies for the same user flags and that forced dotfile replacement is opt-in for
  both preview and apply.
- Added aggregate `maison plan --force-dotfiles` flag-forwarding to match aggregate apply semantics.
- Scoped the builder to user-convergence command-plan construction rather than replacing package-manager behavior or
  broad shell orchestration.
- Made implementation tasks sequential: contract tests first, shared builder implementation second.

### Source Material

- Maison review summary for commit `ded7bbb745f34f1059930fc48eadafe267399ab2`.
- Current Maison documentation under `README.md` and `docs/`.
