# Design — MAISON-004: Private overlay configuration split

## Metadata

- Beads feature root: `maison-mol-e9t`
- Feature slug: `maison-004-private-overlay-configuration`
- Design path: `docs/src/features/maison-004-private-overlay-configuration/design.md`
- Implemented record: `docs/src/features/maison-004-private-overlay-configuration/index.md`
- Base branch: `dev`
- Status: delivered
- Review priority: `P0`

## Feature Summary

Split reusable Maison functionality from personal/site-specific configuration by making a tracked private overlay repository the canonical source for sensitive infrastructure identity and local configuration.

## User Intent

The public control plane must not contain mutable keys or real infrastructure metadata, but Maison must remain durable and easy to replicate. The user described Maison as the vehicle and the private repo as the driver.

## Goals

- Maison remains generic and public-safe.
- A tracked private overlay repo owns real applications, hosts, usernames, emails, deploy targets, dotfiles, preferences, and trusted key material.
- Fresh setup accepts or prompts for the overlay source after Maison bootstraps itself.
- Examples in Maison remain real workable starter configurations without personal data.

## Non-Goals

- Using an untracked-only local inventory as the durable source of truth.
- Using mise secrets as the primary schema for host topology.
- Storing credentials in public Maison.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- Support `--overlay <git-url-or-path>` for bootstrap/setup and prompt only in an interactive terminal.
- Non-interactive setup fails clearly when required overlay input is missing.
- Store selected overlay source in local untracked Maison state and clone or update it into a standard path.
- Validate public Maison examples and private overlays with the same typed schema.
- Mise secrets may provide credentials, tokens, secret values, or the overlay location; typed TOML remains canonical for structured topology and trusted keys.

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

Introduce overlay discovery and loading across Python and Nix. Public Maison keeps schemas, validators, task machinery, templates, examples, and non-personal defaults. A private overlay repo supplies site configuration through typed TOML and optional dotfile trees. Bootstrap accepts `--overlay`, stores the selected source in local state, clones or updates the overlay, and passes overlay paths into validation, Nix evaluation, and mise convergence. Examples remain executable starter configurations with placeholder identities and safe sample hosts.

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

| Exact page                                                            | Create or update        | Planned change                                                                    | Owning Beads task       |
|-----------------------------------------------------------------------|-------------------------|-----------------------------------------------------------------------------------|-------------------------|
| README.md                                                             | Update                  | Align reader-facing contract with MAISON-004: Private overlay configuration split | Implementation tasks    |
| docs/architecture.md                                                  | Update                  | Align reader-facing contract with MAISON-004: Private overlay configuration split | Implementation tasks    |
| docs/operations.md                                                    | Update                  | Align reader-facing contract with MAISON-004: Private overlay configuration split | Implementation tasks    |
| docs/deployment.md                                                    | Update                  | Align reader-facing contract with MAISON-004: Private overlay configuration split | Implementation tasks    |
| docs/add-a-host.md                                                    | Update                  | Align reader-facing contract with MAISON-004: Private overlay configuration split | Implementation tasks    |
| docs/add-a-tool.md                                                    | Update                  | Align reader-facing contract with MAISON-004: Private overlay configuration split | Implementation tasks    |
| docs/add-an-app.md                                                    | Update                  | Align reader-facing contract with MAISON-004: Private overlay configuration split | Implementation tasks    |
| docs/package-policy.md                                                | Update                  | Align reader-facing contract with MAISON-004: Private overlay configuration split | Implementation tasks    |
| docs/task-reference.md                                                | Update                  | Align reader-facing contract with MAISON-004: Private overlay configuration split | Implementation tasks    |
| docs/recovery.md                                                      | Update                  | Align reader-facing contract with MAISON-004: Private overlay configuration split | Implementation tasks    |
| `docs/src/features/maison-004-private-overlay-configuration/index.md` | Create during close-out | Preserve delivery and audit history                                               | Close-out documentation |
| `docs/src/planned-features.md`                                        | Update                  | Track roadmap status and Beads root                                               | Planning                |
| `docs/src/SUMMARY.md`                                                 | Update                  | Register this design and delivered record links                                   | Planning / close-out    |

## Validation Strategy

- Schema tests for public examples and private overlay fixtures.
- Bootstrap tests for `--overlay`, interactive prompt gating, non-interactive failure, local state writes, clone/update behavior, and missing overlay recovery.
- Privacy tests rejecting personal hostnames, usernames, emails, deploy targets, mutable GitHub key URLs, and trusted keys in public Maison defaults.
- `mise -E dev run check` and `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-004-private-overlay-configuration overlay-contract` — Add overlay schema, privacy, and bootstrap contract tests.
- `maison-004-private-overlay-configuration overlay-loader` — Implement private overlay discovery and loading.
- `maison-004-private-overlay-configuration overlay-docs-examples` — Rework docs and examples around public Maison plus private overlay.

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
