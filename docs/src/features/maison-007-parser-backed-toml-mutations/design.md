# Design — MAISON-007: Parser-backed TOML mutations

## Metadata

- Beads feature root: `maison-mol-ywg`
- Feature slug: `maison-007-parser-backed-toml-mutations`
- Design path: `docs/src/features/maison-007-parser-backed-toml-mutations/design.md`
- Implemented record: `docs/src/features/maison-007-parser-backed-toml-mutations/index.md`
- Base branch: `dev`
- Status: draft
- Review priority: `P1`

## Feature Summary

Replace the fragile TOML editor with a formatting-preserving parser-backed mutation layer using pinned `tomlkit`.

## User Intent

A concrete regression proved that `config_edit.py` can delete an unrelated following section when a table header includes a trailing comment.

## Goals

- TOML mutation preserves comments, table boundaries, arrays of tables, quoted keys, and CRLF input.
- Malformed input fails safely without partial writes.
- Authoring commands share one parser-backed mutation layer.

## Non-Goals

- A broad rewrite of all authoring commands before the mutation layer is stable.
- Supporting arbitrary TOML formatting normalization as a side effect.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- Pin `tomlkit` for mutation scripts through a deterministic repository-controlled runtime path that does not rely on ambient Python site-packages.
- Preserve `tool:add` and `tool:remove` repairability when mise project tool resolution is broken; parser-backed editing must still work on the `--skip-tools` path.
- Replace section-splicing logic in `config_edit.py` with parser-backed edits for tools, bootstrap packages/apps, lock entries, and inventory host additions.
- Add regression tests for trailing comments, quoted keys, arrays of tables, CRLF input, unrelated following sections, malformed structures, lock blocks, and host inventory additions.
- Mutation commands write only after successful parse, edit, validation, and lock reconciliation.

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

Introduce a small Python TOML mutation module built on pinned `tomlkit`. Existing TOML authoring surfaces call typed operations for adding and removing tools, bootstrap packages/apps, lock entries, and inventory hosts rather than editing text sections directly. Shell task transaction wrappers and command names remain unchanged.

The `tomlkit` runtime must be deterministic and repository-controlled because `tool:add` and `tool:remove` intentionally bypass mise project tool resolution when repairing invalid tool configuration. The implementation may vendor the exact reviewed `tomlkit` runtime or use an equivalently pinned checked-in dependency mechanism, but it must not depend on unpinned ambient site-packages.

The module preserves formatting where `tomlkit` can round-trip, including comments, quoted keys, table boundaries, arrays of tables, and CRLF newlines covered by tests. Unsupported malformed input is rejected before replacing files. Non-TOML authoring artifacts are outside this feature.

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

| Exact page                                                           | Create or update        | Planned change                                                                                | Owning Beads task       |
|----------------------------------------------------------------------|-------------------------|-----------------------------------------------------------------------------------------------|-------------------------|
| docs/src/development/tooling.md                                      | Update                  | Document the pinned parser-backed TOML mutation runtime for contributors                      | Implementation tasks    |
| docs/task-reference.md                                               | Update                  | Document parser-backed transactional TOML mutation guarantees for configuration commands      | Implementation tasks    |
| docs/add-a-tool.md                                                   | Update                  | Explain tool/package edits preserve supported TOML formatting and fail without partial writes | Implementation tasks    |
| docs/add-an-app.md                                                   | Update                  | Explain app edits preserve supported TOML formatting and fail without partial writes          | Implementation tasks    |
| `docs/src/features/maison-007-parser-backed-toml-mutations/index.md` | Create during close-out | Preserve delivery and audit history                                                           | Close-out documentation |
| `docs/src/planned-features.md`                                       | Update                  | Track roadmap status and Beads root                                                           | Planning                |
| `docs/src/SUMMARY.md`                                                | Update                  | Register this design and delivered record links                                               | Planning / close-out    |

## Validation Strategy

- Focused `tests/test_config_edit.py` regression corpus for comments, quoted keys, arrays of tables, CRLF input, malformed TOML, lock blocks, host inventory additions, and unrelated sections.
- Tests proving the pinned `tomlkit` runtime is used without ambient site-packages and remains available on the `tool:add`/`tool:remove` `--skip-tools` path.
- Behavioral authoring command tests.
- `mise -E dev run check` and `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-007-parser-backed-toml-mutations toml-contract` — Add parser-backed TOML regression corpus.
- `maison-007-parser-backed-toml-mutations toml-implementation` — Replace text-splice TOML editing with pinned tomlkit layer.

## Dependencies and Parallelism

This feature follows the Maison review order. Its implementation tasks depend on specification reconciliation. The
contract task blocks the implementation task so regression coverage lands first. The two planned implementation tasks
are not parallel-safe because both touch the mutation helper, authoring behavior, and related tests/docs.

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
