# Design — MAISON-010: Shared inventory schema validation

## Metadata

- Beads feature root: `maison-mol-bvr`
- Feature slug: `maison-010-shared-inventory-schema`
- Design path: `docs/src/features/maison-010-shared-inventory-schema/design.md`
- Implemented record: `docs/src/features/maison-010-shared-inventory-schema/index.md`
- Base branch: `dev`
- Status: reviewed
- Review priority: `P1`

## Feature Summary

Make Python and Nix inventory validation identical through one schema source and shared valid/invalid fixture corpus.

## User Intent

The Python and Nix implementations disagree about duplicate profiles, unknown features, types, and accepted fields.

## Goals

- One checked-in public schema contract drives both Python and Nix validation.
- Shared valid and invalid fixtures cover public examples and private overlay shapes.
- Drift between Python and Nix validators fails CI.

## Non-Goals

- Replacing TOML as the inventory format.
- Encoding actual private inventory in the public repo.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- Define `schemas/inventory.toml` as the public inventory schema contract owned by Maison.
- Python and Nix validation load schema data from that contract rather than duplicating allowed systems, profiles,
  feature keys, deploy fields, and defaults in separate source code.
- Python and Nix validation consume the same fixture corpus under `tests/fixtures/inventory/`.
- Fixtures cover duplicate profiles, unknown features, unknown deploy fields, type errors, accepted fields, overlay
  inventory and host-override layout, and deploy path constraints.
- Docs describe inventory fields, defaults, constraints, overlay inventory validation, and host override layout.

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

Create `schemas/inventory.toml` as the canonical public schema contract. The file contains schema version, supported
systems, profile names, feature keys and defaults, deploy keys and defaults, and the portable validation policy that both
validators must enforce. Python remains the ergonomic typed reader, while Nix imports the same contract with
`builtins.fromTOML` and uses it before constructing outputs.

Add a canonical fixture corpus under `tests/fixtures/inventory/` with valid and invalid TOML inventories plus minimal
expected-result metadata. CI runs Python and Nix validators against every fixture so divergence fails before deployment
or authoring changes land. Overlay fixtures model an active overlay inventory and sibling `hosts/` override layout; they
do not merge public and private inventories.

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

- `schemas/inventory.toml` becomes the single public schema contract for inventory validation data.
- The shared fixture corpus is an executable compatibility contract for both Python and Nix validators.

### Architecture Documentation Changes

Update the architecture and operations pages named in **Documentation Impact** so current reader-facing docs match the
implemented behavior.

## Operational Considerations

Operators should receive explicit errors, recovery instructions, and validation evidence for this feature's failure
modes. Recovery docs must distinguish Nix generation behavior, repository/source behavior, user convergence behavior,
and external package-manager side effects when those concerns apply.

## Documentation Impact

| Exact page                                                      | Create or update        | Planned change                                                                | Owning Beads task       |
|-----------------------------------------------------------------|-------------------------|-------------------------------------------------------------------------------|-------------------------|
| docs/architecture.md                                            | Update                  | Document `schemas/inventory.toml` as the shared inventory schema contract     | Implementation tasks    |
| docs/add-a-host.md                                              | Update                  | Document inventory authoring constraints and overlay host override validation | Implementation tasks    |
| docs/deployment.md                                              | Update                  | Document deploy inventory fields and shared validation constraints            | Implementation tasks    |
| docs/src/reference/inventory.md                                 | Create                  | Define inventory fields, defaults, constraints, and fixture contract          | Implementation tasks    |
| docs/src/reference/tooling.md                                   | Update                  | Mention shared inventory schema and fixture validation tooling                | Implementation tasks    |
| `docs/src/features/maison-010-shared-inventory-schema/index.md` | Create during close-out | Preserve delivery and audit history                                           | Close-out documentation |
| `docs/src/planned-features.md`                                  | Update                  | Track roadmap status and Beads root                                           | Planning                |
| `docs/src/SUMMARY.md`                                           | Update                  | Register this design and delivered record links                               | Planning / close-out    |

## Validation Strategy

- Shared fixture corpus executed by Python tests and Nix checks.
- Coverage for active overlay inventory and host override layout, public example inventory, and deploy path constraints.
- `mise -E dev run check` and `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-010-shared-inventory-schema schema-fixtures` — Add shared inventory schema contract and validation fixture corpus.
- `maison-010-shared-inventory-schema schema-implementation` — Load the shared schema contract from Python and Nix validators.

## Dependencies and Parallelism

This feature follows the Maison review order. Its implementation tasks depend on specification reconciliation. The
schema implementation depends on the schema-fixtures task because the fixture corpus is the executable contract; these
tasks are sequential because they edit the same validation tests and documentation pages.

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

- Named `schemas/inventory.toml` as the canonical public schema contract for shared validation data.
- Replaced ambiguous overlay merge wording with active overlay inventory and host override layout fixtures.
- Added an inventory reference page to document exact fields, defaults, constraints, and fixture contracts.
- Made schema implementation depend on fixture-contract work so tests define the compatibility boundary first.

### Source Material

- Maison review summary for commit `ded7bbb745f34f1059930fc48eadafe267399ab2`.
- Current Maison documentation under `README.md` and `docs/`.
