# Design — MAISON-014: Remote convergence restoration

## Metadata

- Beads feature root: `maison-mol-vhhy`
- Feature slug: `maison-014-remote-convergence-restoration`
- Design path: `docs/src/features/maison-014-remote-convergence-restoration/design.md`
- Implemented record: `docs/src/features/maison-014-remote-convergence-restoration/index.md`
- Base branch: `dev`
- Status: draft
- Review priority: `P1`

## Feature Summary

Restore user state after failed remote convergence by rerunning restricted convergence from the restored prior repository.

## User Intent

A failed deployment restores repository source but can leave links and other user state pointing at the failed revision.

## Goals

- After remote user convergence failure, restore prior repository source and reconverge user state from that revision.
- Restrict recovery convergence to reversible user state.
- Report irreversible package-side effects separately.

## Non-Goals

- Guaranteeing package-manager rollback for completed external package operations.
- Rolling back the Nix system profile outside deploy-rs semantics.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

When `maison deploy <host>` reaches remote user convergence and that phase fails, Maison first completes and verifies the
repository transaction rollback. Only after the restored repository revision is verified does it run restricted recovery
as the managed user from that restored repository. Recovery writes a JSON diagnostic under
`~/.local/state/maison/recovery/` and reports its path. The deployment preserves the original user-convergence exit
status; a rollback failure prevents recovery, and a recovery failure is reported separately with both statuses retained
in the diagnostic.

## Requirements

### Functional Requirements

- The failed remote user-convergence path completes repository rollback and verifies the restored prior revision before
  attempting any recovery convergence.
- Recovery runs as the managed user from the restored repository. The deployment account remains responsible only for
  the privileged transaction recovery and does not run user-owned convergence.
- Restricted recovery repairs dotfile convergence, mise lock links, non-package mise user state, and Maison-owned user
  finalization. It honors the deployment's explicit `--force-dotfiles` choice and never enables force implicitly.
- Restricted recovery does not run `user:apply`, `user-apply-packages.sh`, package/app bootstrap, application-backup
  migration, legacy Git migration, system activation, or Nix rollback.
- Recovery writes an atomically replaced mode-0600 JSON report at
  `~/.local/state/maison/recovery/remote-convergence-<failed-revision>.json`. The version-one report contains
  `schema_version`, `kind`, `failed_revision`, `restored_revision`, `initial_convergence` (exit code and package-phase
  status), `recovery` (status, exit code, steps, and force-dotfiles state), and `external_side_effects`. The latter
  records package/app convergence as not rolled back and whether follow-up work is required.
- Package/app side effects are reported as `not-started`, `started`, `completed`, `failed`, or `unknown` based on the
  observed convergence step; the report never claims that an external package manager was rolled back.
- If repository rollback fails, recovery is skipped and the command reports the transaction inspection path. If rollback
  succeeds, the original user-convergence failure remains the deployment's exit status even when recovery succeeds;
  recovery failure is included in stderr and the JSON report.
- Docs distinguish repository rollback, restricted user reconvergence, and package/app side effects.

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

Add a post-rollback recovery phase to the existing remote deployment path. The current full user convergence remains the
first attempt. When it fails, the deployment account invokes the existing repository transaction finalizer with
`rollback`; the finalizer verifies the active failed revision, restores the prior repository, and removes transaction
state only after the swap is durable. The deployment then invokes recovery over SSH as the managed user from that
restored repository. A failed rollback never runs recovery.

Extend `.mise/lib/user_convergence.py` with an internal `recovery` mode instead of creating a second convergence
pipeline. Recovery uses the existing command-plan ownership and ordering, with this explicit safe set:

1. dotfile conflict preparation/convergence, limited to the existing explicit force policy and without application
   archival or legacy Git migration;
2. mise lockfile linking;
3. non-package mise user state; and
4. Maison-owned user finalization.

The recovery plan excludes `user-apply-packages.sh`, all `bootstrap.packages` and app convergence, system tasks, and
broad `user:apply`. The planner records step transitions so the deployment can distinguish whether external package/app
convergence was not started, started, completed, failed, or could not be determined. It writes the report through a
user-owned temporary file and atomic rename; no new privileged transaction namespace is introduced.

The remote wrapper preserves the original convergence status, runs recovery only after successful repository rollback,
and emits the report path and recovery status without hiding either failure. The report's package/app entry is a
follow-up diagnostic, not a promise of external rollback.

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

| Exact page                                                             | Create or update        | Planned change                                                                                                           | Owning Beads task           |
|------------------------------------------------------------------------|-------------------------|--------------------------------------------------------------------------------------------------------------------------|-----------------------------|
| docs/deployment.md                                                     | Update                  | Document rollback-before-recovery ordering, managed-user execution, report path, and original/recovery failure semantics | `reconverge-implementation` |
| docs/recovery.md                                                       | Update                  | Document restricted recovery steps, skipped package/app rollback, report fields, and manual follow-up                    | `reconverge-implementation` |
| docs/operations.md                                                     | Update                  | Document the automatic recovery outcome and explicit `--force-dotfiles` behavior                                         | `reconverge-implementation` |
| docs/task-reference.md                                                 | Update                  | Reference deploy's restricted recovery contract and diagnostic artifact                                                  | `reconverge-implementation` |
| `docs/src/features/maison-014-remote-convergence-restoration/index.md` | Create during close-out | Preserve delivery and audit history                                                                                      | Close-out documentation     |
| `docs/src/planned-features.md`                                         | Update                  | Mark the roadmap state and retain the Beads root after delivery                                                          | Close-out documentation     |
| `docs/src/SUMMARY.md`                                                  | Update                  | Register the delivered record while retaining the design link                                                            | Close-out documentation     |

## Validation Strategy

- Add fault-injection tests in `tests/test_remote_convergence.py` for failed user convergence, rollback-before-recovery,
  restored-revision execution, force-dotfile forwarding, report contents, skipped package/app convergence, and separate
  recovery failure.
- Run focused tests for `tests.test_remote_convergence`, `tests.test_deployment_contracts`, and
  `tests.test_user_convergence`.
- Run `python3 scripts/check-docs.py` after reader-facing documentation changes.
- Run `mise run check` for repository-wide validation.

## Implementation Decomposition

- `maison-014-remote-convergence-restoration reconverge-contract` — Create
  `tests/test_remote_convergence.py` with behavioral/fault-injection coverage for the exact recovery sequence,
  revision boundary, safe-step exclusion, report schema/statuses, force forwarding, and failure semantics. This task
  owns no production source or reader-facing docs.
- `maison-014-remote-convergence-restoration reconverge-implementation` — Update `.mise/tasks/deploy`,
  `.mise/lib/user_convergence.py`, and the narrowly scoped user-prepare adapter needed for recovery; update
  `docs/deployment.md`, `docs/recovery.md`, `docs/operations.md`, and `docs/task-reference.md`; run focused and broad
  validation; preserve the existing transaction and Nix/mise ownership boundaries.

## Dependencies and Parallelism

This feature follows the Maison review order. The implementation coordinator and both implementation children depend
on specification reconciliation. The contract-test child completes before the implementation child so tests establish
the behavior before production changes. The contract-test child owns only its new test file; the implementation child
owns production source and the four reader-facing pages, so no sibling edits overlap.

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
