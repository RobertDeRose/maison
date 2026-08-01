# Design — MAISON-016: Pi TypeScript validation boundary

## Metadata

- Beads feature root: `maison-mol-fmud`
- Feature slug: `maison-016-pi-typescript-validation`
- Design path: `docs/src/features/maison-016-pi-typescript-validation/design.md`
- Implemented record: `docs/src/features/maison-016-pi-typescript-validation/index.md`
- Base branch: `dev`
- Status: draft
- Review priority: `P1`

## Feature Summary

Add a real TypeScript workspace, Pi types, typecheck, pure modules, and behavioral tests for Pi extensions.

## User Intent

The Pi extensions include a 983-line pager without a pinned TypeScript workspace, typecheck, or behavioral tests.

## Goals

- Pi extension TypeScript is typechecked with pinned tooling.
- Pure pager logic is separated from terminal integration.
- Tests cover Unicode, ANSI handling, navigation, timers, and terminal resizing.

## Non-Goals

- Rewriting Pi itself.
- Changing visual design beyond behavior needed for tests and type boundaries.

## User-Facing Behavior

Operators keep using `maison` and mise tasks as the command surface. The feature changes the underlying safety,
validation, or documentation contract named above without requiring operators to learn an unrelated tool. When behavior
is unsafe or unsupported, Maison fails with an actionable message instead of silently continuing.

## Requirements

### Functional Requirements

- Add a pinned TypeScript workspace for `dotfiles/pi/extensions` or an equivalent project-local package.
- Use actual Pi types or local checked interface definitions derived from documented Pi extension APIs.
- Run `tsc --noEmit` in Maison validation.
- Add behavioral tests for pure pager modules.

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

Create a private project-local Node workspace at `dotfiles/pi/extensions`. The workspace is source for validation only;
Mise continues to symlink the extension `.ts` files into the user's Pi directory, while `package.json`,
`package-lock.json`, and `tsconfig.json` remain repository-owned workspace metadata. The root `mise.toml` owns Node 24
for repository checks. The workspace lock pins TypeScript, `tsx`, `@types/node`, and the Pi packages used by the
extensions (`@earendil-works/pi-ai`, `@earendil-works/pi-coding-agent`, and `@earendil-works/pi-tui`); validation does
not depend on the macOS-only global Pi installation.

Add a `check:typescript` task that runs `npm ci --ignore-scripts` in the workspace, then invokes the package scripts
`tsc --noEmit` and the focused `node:test` suite through the pinned `tsx` runner. Include this task in the repository
`check` task so CI and local validation use the same boundary.

Extract only the pager logic needed for deterministic tests: `pager/markdown.ts` owns newline normalization, fenced
code, and heading/numbering extraction; `pager/keys.ts` owns key and printable-input decoding; and
`pager/navigation.ts` owns scroll, TOC, and code-block selection state transitions. These modules must not import Pi,
TUI, clipboard, process, or terminal APIs. `pager.ts` remains the thin rendering, clipboard, timer, and Pi-registration
adapter. Timer behavior is tested through an injected scheduler/fake-timer seam rather than wall-clock sleeps. No
visual redesign or wholesale pager rewrite is part of this feature.

## Architecture Consistency

### Existing Patterns Reused

- Nix/Lix remains the privileged system layer.
- mise remains the user command and package/dotfile layer.
- `maison check` remains the repository-wide validation entrypoint.
- Python is the preferred home for stateful behavior that needs tests, parsing, locks, manifests, or recovery.

### Invariants Preserved

- A file, package, service, or preference has exactly one owner within its execution scope. Node is the deliberate scoped
  exception: the global user runtime serves standalone Pi, while repository Node 24 serves locked validation without
  changing global convergence.
- Intel macOS remains unsupported.
- Remote deployment remains split between deploy-rs system-profile handling and Maison repository/user handling.
- Public Maison does not contain private infrastructure identity or trusted access material.

### New Decisions Introduced

- This feature adopts the concrete behavior described in **Proposed Design** as the supported Maison contract.

### Architecture Documentation Changes

Update the exact reader-facing pages named in **Documentation Impact**. The architecture page records the scoped Node
runtime boundary; development and reference tooling pages explain workspace installation and validation commands;
`dotfiles/pi/AGENTS.md` explains the extension editing and test boundary; and `dotfiles/opencode/README.md` records that
the workspace is scoped to Pi extensions and does not change OpenCode runtime configuration. No operations page requires a
behavior change for this feature.

## Operational Considerations

Operators should receive explicit errors, recovery instructions, and validation evidence for this feature's failure
modes. Recovery docs must distinguish Nix generation behavior, repository/source behavior, user convergence behavior,
and external package-manager side effects when those concerns apply.

## Documentation Impact

| Exact page                                                       | Create or update        | Planned change                                                                  | Owning Beads task       |
|------------------------------------------------------------------|-------------------------|---------------------------------------------------------------------------------|-------------------------|
| docs/architecture.md                                             | Update                  | Document the scoped repository Node runtime used for Pi validation              | Implementation tasks    |
| docs/src/development/tooling.md                                  | Update                  | Align reader-facing contract with MAISON-016: Pi TypeScript validation boundary | Implementation tasks    |
| docs/src/reference/tooling.md                                    | Update                  | Align reader-facing contract with MAISON-016: Pi TypeScript validation boundary | Implementation tasks    |
| dotfiles/pi/AGENTS.md                                            | Update                  | Align reader-facing contract with MAISON-016: Pi TypeScript validation boundary | Implementation tasks    |
| dotfiles/opencode/README.md                                      | Update                  | Align reader-facing contract with MAISON-016: Pi TypeScript validation boundary | Implementation tasks    |
| `docs/src/features/maison-016-pi-typescript-validation/index.md` | Create during close-out | Preserve delivery and audit history                                             | Close-out documentation |
| `docs/src/planned-features.md`                                   | Update                  | Track roadmap status and Beads root                                             | Planning                |
| `docs/src/SUMMARY.md`                                            | Update                  | Register this design and delivered record links                                 | Planning / close-out    |

## Validation Strategy

- `mise run check:typescript`, which performs locked workspace installation, `tsc --noEmit`, and the focused
  `node:test` suite for Pi extensions.
- Behavioral tests for Unicode, ANSI handling, navigation, deterministic timers, and terminal resizing.
- `mise -E dev run check` and `uv run scripts/check-docs.py`.

## Implementation Decomposition

- `maison-016-pi-typescript-validation typescript-workspace` — Own the project-local package metadata, root Node/mise
  check wiring, Pi type dependencies, typecheck task, and the exact tooling/agent documentation pages.
- `maison-016-pi-typescript-validation pager-tests` — After the workspace exists, extract the named pure pager modules
  and add deterministic `node:test` coverage for Unicode, ANSI, navigation, timers, and terminal resizing.

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
