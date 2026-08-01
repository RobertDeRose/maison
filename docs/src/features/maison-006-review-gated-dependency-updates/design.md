# Design — MAISON-006: Review-gated dependency updates

## Metadata

- Beads feature root: `maison-mol-aqu`
- Feature slug: `maison-006-review-gated-dependency-updates`
- Design path: `docs/src/features/maison-006-review-gated-dependency-updates/design.md`
- Implemented record: `docs/src/features/maison-006-review-gated-dependency-updates/index.md`
- Base branch: `dev`
- Status: delivered
- Review priority: `P0`

## Feature Summary

Stop administratively auto-merging dependency updates by separating cache warming from dependency approval and requiring normal branch protection and review.

## User Intent

The cache-refresh workflow uses an administrative bypass to merge flake updates.

## Goals

- Automated cache refresh never admin-merges dependency updates.
- Flake update PRs require ordinary review and branch protection.
- Cache warming remains available without approving dependency changes.

## Non-Goals

- Removing automated PR creation.
- Changing Nix input semantics.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- Remove `gh pr merge --admin` or equivalent administrative bypass from workflows.
- Separate cache-warming jobs from dependency-update approval jobs.
- Docs state review requirements and cache behavior.
- CI tests or workflow linting catch reintroduction of admin merge.

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

Update `.github/workflows/cache-refresh.yml` so cache realization and dependency approval are separate. Automation may update `flake.lock`, build the proposed closure matrix, warm Cachix, and open or update an `automation/refresh-flake-lock` pull request after cache warming succeeds. It must not merge that PR, use `gh pr merge --admin`, enable auto-merge, or otherwise bypass ordinary branch protection.

GitHub pull request review and protected-branch checks remain the only dependency approval mechanism. This feature does not introduce a second approval service or a new operator command. Cache warming can run against proposed dependency changes without granting approval; accepting the dependency update remains a normal reviewed PR merge.

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

| Exact page                                                              | Create or update        | Planned change                                                                                                   | Owning Beads task       |
|-------------------------------------------------------------------------|-------------------------|------------------------------------------------------------------------------------------------------------------|-------------------------|
| docs/operations.md                                                      | Update                  | Explain that automated cache warming may prepare a flake update PR, but dependency approval remains review-gated | Implementation tasks    |
| docs/src/development/tooling.md                                         | Update                  | Document cache-refresh workflow behavior for contributors and CI maintainers                                     | Implementation tasks    |
| docs/src/reference/tooling.md                                           | Update                  | List `.github/workflows/cache-refresh.yml` and its no-admin-merge contract                                       | Implementation tasks    |
| `docs/src/features/maison-006-review-gated-dependency-updates/index.md` | Create during close-out | Preserve delivery and audit history                                                                              | Close-out documentation |
| `docs/src/planned-features.md`                                          | Update                  | Track roadmap status and Beads root                                                                              | Planning                |
| `docs/src/SUMMARY.md`                                                   | Update                  | Register this design and delivered record links                                                                  | Planning / close-out    |

## Validation Strategy

- Workflow tests or source guards reject `--admin` merge, auto-merge enablement, and any dependency-automation job that invokes `gh pr merge`.
- Workflow tests or source guards prove cache warming can run without granting dependency approval and that update PR creation/update remains separate from merge approval.
- Actionlint on updated workflows.
- `mise -E dev run check` and `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-006-review-gated-dependency-updates ci-contract` — Add dependency-update workflow safety checks.
- `maison-006-review-gated-dependency-updates ci-implementation` — Separate cache warming from dependency approval.

## Dependencies and Parallelism

This feature follows the Maison review order. Its implementation tasks depend on specification reconciliation. The
contract task blocks the implementation task so workflow safety guards land before the workflow change. The two planned
implementation tasks are not parallel-safe because both touch workflow safety expectations and related tests/docs.

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
