# Design — MAISON-011: Bounded deterministic test suite

## Metadata

- Beads feature root: `maison-mol-8mr`
- Feature slug: `maison-011-deterministic-test-suite`
- Design path: `docs/src/features/maison-011-deterministic-test-suite/design.md`
- Implemented record: `docs/src/features/maison-011-deterministic-test-suite/index.md`
- Base branch: `dev`
- Status: reviewed
- Review priority: `P1`

## Feature Summary

Make the test suite bounded and deterministic with subprocess timeouts, process-group cleanup, captured diagnostics, and subsystem splits.

## User Intent

The main test file is 1,727 lines with 48 external-process calls and no timeout. Repeated bounded full-suite runs did not complete reliably.

## Goals

- Every external process in tests has a timeout and process-group cleanup.
- Tests are split by subsystem.
- Diagnostics are captured without unbounded output.
- Source-text assertions become behavioral tests where practical.

## Non-Goals

- Removing coverage for deployment or Nix behavior.
- Broadly rewriting production code solely for test organization.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- Introduce a stdlib-only test subprocess helper with timeout, process-group termination, stdout/stderr capture,
  concise failure diagnostics, and temporary-directory isolation.
- Refactor tests into subsystem files without changing covered behavior.
- Bound every external test process through the helper. The default subprocess timeout is 30 seconds; longer per-call
  timeouts must be explicit, documented at the call site, and no longer than 300 seconds.
- Keep `check:tests` deterministic and expected to complete within five minutes on a warm supported development
  checkout; document focused validation partitions for subsystem work.
- Replace fragile source-text assertions with behavioral checks when an executable contract exists.

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

Add a shared stdlib test subprocess helper and migrate external process calls to it. The helper starts commands in an
isolated process group where the platform supports it, terminates the whole group on timeout, captures stdout and stderr,
truncates diagnostics to a documented size, and accepts an explicit timeout override for known long-running Nix or Git
fixtures.

Split the monolithic topology suite into inventory, deployment, ownership, transaction, repository, and migration test
files. Keep fixtures isolated per test and capture concise diagnostics for failures. Update development docs with
focused subsystem commands, the helper timeout policy, and the expected full-suite bound.

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

- Tests that execute external commands use a shared stdlib subprocess helper rather than ad hoc `subprocess` calls.
- Test modules are organized by Maison subsystem so focused validation commands map to the area being changed.

### Architecture Documentation Changes

Update the architecture and operations pages named in **Documentation Impact** so current reader-facing docs match the
implemented behavior.

## Operational Considerations

Operators should receive explicit errors, recovery instructions, and validation evidence for this feature's failure
modes. Recovery docs must distinguish Nix generation behavior, repository/source behavior, user convergence behavior,
and external package-manager side effects when those concerns apply.

## Documentation Impact

| Exact page                                                       | Create or update        | Planned change                                                                                      | Owning Beads task       |
|------------------------------------------------------------------|-------------------------|-----------------------------------------------------------------------------------------------------|-------------------------|
| docs/src/development/tooling.md                                  | Update                  | Document bounded test helper behavior, focused subsystem test commands, and full-suite expectations | Implementation tasks    |
| docs/src/reference/tooling.md                                    | Update                  | Define validation partitions, subprocess timeout policy, and the shared test helper contract        | Implementation tasks    |
| docs/operations.md                                               | Update                  | Summarize operator/contributor validation commands and bounded check expectations                   | Implementation tasks    |
| `docs/src/features/maison-011-deterministic-test-suite/index.md` | Create during close-out | Preserve delivery and audit history                                                                 | Close-out documentation |
| `docs/src/planned-features.md`                                   | Update                  | Track roadmap status and Beads root                                                                 | Planning                |
| `docs/src/SUMMARY.md`                                            | Update                  | Register this design and delivered record links                                                     | Planning / close-out    |

## Validation Strategy

- Focused tests for the subprocess helper itself.
- Full `mise -E dev run check` completes within the documented bound.
- `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-011-deterministic-test-suite test-helper` — Add the bounded subprocess helper and focused helper tests.
- `maison-011-deterministic-test-suite test-suite-split` — Split subsystem tests, migrate existing external process
  calls to the helper, and update validation documentation.

## Dependencies and Parallelism

This feature follows the Maison review order. Both implementation tasks depend on specification reconciliation. The
suite-split task depends on the helper task because existing external process calls must migrate to that shared helper
and both tasks touch tests and validation documentation. The implementation tasks are sequential.

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

- Corrected documentation impact paths to the mdBook source pages under `docs/src/development/` and
  `docs/src/reference/`.
- Made the test subprocess contract explicit: default 30 second timeout, documented explicit overrides up to 300 seconds,
  process-group cleanup, bounded diagnostics, and `check:tests` expected to finish within five minutes on a warm
  supported development checkout.
- Clarified that the subprocess helper is stdlib-only and test-local, and that implementation tasks are sequential:
  helper first, suite split and migration second.

### Source Material

- Maison review summary for commit `ded7bbb745f34f1059930fc48eadafe267399ab2`.
- Current Maison documentation under `README.md` and `docs/`.
