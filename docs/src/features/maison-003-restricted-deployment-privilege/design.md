# Design — MAISON-003: Restricted deployment privilege model

## Metadata

- Beads feature root: `maison-mol-4v3`
- Feature slug: `maison-003-restricted-deployment-privilege`
- Design path: `docs/src/features/maison-003-restricted-deployment-privilege/design.md`
- Implemented record: `docs/src/features/maison-003-restricted-deployment-privilege/index.md`
- Base branch: `dev`
- Status: draft
- Review priority: `P0`
- Review status: reconciled in /start-feature (documentation and design reviews complete)

## Feature Summary

Replace unrestricted passwordless sudo and direct root deployment defaults with a dedicated `maison-deploy` account and narrowly scoped privileged commands.

## User Intent

The current Linux model combines remotely sourced user keys with `NOPASSWD: ALL`, making a user-key compromise a root compromise.

## Goals

- Use `maison-deploy` as the default privileged deployment account.
- Separate deployment identity from the managed user.
- Restrict privileged commands to reviewed Maison deployment helpers and deploy-rs activation requirements.
- Remove `NOPASSWD: ALL` from supported defaults.

## Non-Goals

- Supporting arbitrary third-party deployment privilege brokers.
- Weakening deploy-rs profile activation checks.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- Inventory and Nix validation model `maison-deploy` separately from the managed user.
- Sudoers grants are command-scoped and argument-bounded for Maison privileged helpers.
- Direct root deployment is not the default path.
- Docs explain account roles, trust boundaries, and recovery.

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

Introduce a Linux deployment account named `maison-deploy`. System-manager config creates or validates that account, installs reviewed authorized keys from the private overlay, and grants only the commands needed for deploy-rs activation plus Maison transaction finalization and recovery. User convergence still runs as the managed user. The deployment adapter connects through the deployment account by default and refuses inventory that grants unmanaged `NOPASSWD: ALL`.

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

| Exact page                                                              | Create or update        | Planned change                                                                      | Owning Beads task       |
|-------------------------------------------------------------------------|-------------------------|-------------------------------------------------------------------------------------|-------------------------|
| docs/architecture.md                                                    | Update                  | Align reader-facing contract with MAISON-003: Restricted deployment privilege model | Implementation tasks    |
| docs/deployment.md                                                      | Update                  | Align reader-facing contract with MAISON-003: Restricted deployment privilege model | Implementation tasks    |
| docs/recovery.md                                                        | Update                  | Align reader-facing contract with MAISON-003: Restricted deployment privilege model | Implementation tasks    |
| docs/task-reference.md                                                  | Update                  | Align reader-facing contract with MAISON-003: Restricted deployment privilege model | Implementation tasks    |
| docs/add-a-host.md                                                      | Update                  | Align reader-facing contract with MAISON-003: Restricted deployment privilege model | Implementation tasks    |
| `docs/src/features/maison-003-restricted-deployment-privilege/index.md` | Create during close-out | Preserve delivery and audit history                                                 | Close-out documentation |
| `docs/src/planned-features.md`                                          | Update                  | Track roadmap status and Beads root                                                 | Planning                |
| `docs/src/SUMMARY.md`                                                   | Update                  | Register this design and delivered record links                                     | Planning / close-out    |

## Validation Strategy

- Nix and Python inventory tests for separate deployment and managed users.
- Text and behavioral tests rejecting `NOPASSWD: ALL` defaults and direct root deployment defaults.
- Deployment adapter tests proving privileged command allowlist construction.
- `mise -E dev run check` and `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-003-restricted-deployment-privilege privilege-contract` — Add deployment-account and sudoers contract tests.
- `maison-003-restricted-deployment-privilege privilege-implementation` — Implement `maison-deploy` restricted privilege model.

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
