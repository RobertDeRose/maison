# MAISON-016: Pi TypeScript validation boundary

## Delivery Summary

- Beads feature root: `maison-mol-fmud`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison now validates its Pi extensions through a repository-owned TypeScript workspace. The workspace pins the Pi API
packages, TypeScript compiler, test runner, and Node type definitions without changing the files symlinked into the
user's Pi installation. The 983-line pager now delegates pure Markdown parsing, key decoding, navigation, timer, and
terminal-layout behavior to testable modules.

## User-Facing Behavior

Operators and contributors keep the existing Maison and Pi command surfaces. Repository validation now includes:

```bash
mise run check:typescript
```

The task installs the committed npm lockfile without lifecycle scripts, runs `tsc --noEmit`, executes the focused
behavioral tests, and removes its local dependency tree before downstream repository and Nix checks. Direct iteration
is available from `dotfiles/pi/extensions` with `npm ci --ignore-scripts --no-audit --no-fund`, `npm run typecheck`, and
`npm test`.

Pi extension registration, existing command names, clipboard behavior, and pager rendering remain in `pager.ts`. The
workspace metadata is validation-only and is not installed as a Pi runtime file. The global Node runtime remains the
standalone Pi runtime; repository `mise.toml` pins Node 24 within the checkout for reproducible validation.

## Design Integration

The implementation keeps Nix/Lix as the privileged system layer and mise as the repository/user tooling layer. Actual
Pi package declarations supply the extension types, while the project-local npm lockfile supplies reproducible
validation dependencies. `pager/markdown.ts`, `pager/keys.ts`, and `pager/navigation.ts` do not import Pi, TUI,
clipboard, process, or terminal APIs. `pager.ts` remains the integration adapter for rendering and runtime events.

The scoped Node runtime exception is documented explicitly: global configuration serves standalone Pi, and the
repository configuration serves locked validation without replacing global user convergence.

## Operational Impact

Contributors should run `mise run check:typescript` after changing Pi extensions. The command may access the npm registry
to install the committed dependency lock, but ignores package lifecycle scripts and cleans `node_modules` before exiting.
This cleanup keeps generated third-party JSON out of repository data validation and prevents Nix source evaluation from
traversing the local dependency tree. No Pi or OpenCode runtime configuration is changed by the workspace.

## Reference and Contracts

- [Architecture](../../architecture.md)
- [Developer tooling](../../development/tooling.md)
- [Tooling reference](../../reference/tooling.md)
- Pi contributor guidance: `dotfiles/pi/AGENTS.md`
- OpenCode boundary: `dotfiles/opencode/README.md`
- [Feature design](design.md)

## Validation Evidence

- `mise run check:typescript` — passed: `tsc --noEmit` and 10 focused behavioral tests.
- `uv run scripts/check-docs.py` — passed after documentation reconciliation.
- `shellcheck .mise/tasks/check/_default .mise/tasks/check/typescript` — passed.
- `git diff --check` — passed.
- `mise -E dev run check` — passed: 152 Python tests plus data, shell, and Nix checks.
- Pure-module boundary inspection — passed: pager modules contain no Pi, TUI, process, or terminal imports.

## Design Reconciliation

### Delivered as Designed

- Added a private project-local Node workspace with pinned Pi packages, TypeScript, `tsx`, and Node types.
- Wired `tsc --noEmit` and focused `node:test` execution into the Maison check task.
- Extracted pure Markdown, key-decoding, navigation, timer-scheduling, and terminal-layout behavior.
- Added behavioral coverage for Unicode, ANSI handling, fenced code, heading numbering, keyboard protocols, navigation,
  TOC selection, code blocks, deterministic timers, and terminal resizing.
- Preserved the existing Pi registration adapter, commands, and runtime ownership boundaries.

### Intentional Changes

- Repository Node 24 is a scoped validation override while global configuration retains the standalone Pi runtime. The
  ownership test and architecture documentation now describe this boundary explicitly.
- The TypeScript validation task removes its temporary npm dependency tree on exit so repository data and Nix checks do
  not inspect third-party files.
- `check:data` skips `node_modules` defensively for any local Node workspace, while committed package and lock metadata
  remain validated normally.

### Deferred Work

- Pull-request and merge metadata remain pending the delivery action selected after close-out.
- No interactive Pi host integration environment was available; typechecking and pure behavioral tests cover the
  delivered validation boundary without launching the full Pi UI.

### Rejected or Removed Scope

- No visual pager redesign or wholesale pager rewrite was added.
- No alternate Pi registration path, OpenCode runtime configuration, or package-manager convergence path was introduced.
- No Home Manager, Nix system ownership, supported-platform, or user-command boundary changes were made.

## Documentation Updated

- `docs/architecture.md`
- `docs/src/development/tooling.md`
- `docs/src/features/maison-016-pi-typescript-validation/design.md`
- `docs/src/features/maison-016-pi-typescript-validation/index.md`
- `docs/src/reference/tooling.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`
- `dotfiles/pi/AGENTS.md`
- `dotfiles/opencode/README.md`

## Audit Trail

- Specification reconciliation and reviewed design: `maison-mol-40gy`, commit `4e79de64c8505f50a58cef918b8981458ff4219f`.
- Workspace implementation: `maison-mol-1h4n.1`, commit `6c7328397ff54fb51eea15e4fb7b4f977e3e6a33`.
- Pager modules and behavioral tests: `maison-mol-1h4n.2`, commit `65fdd7398a4315ff5ab0db4944d8339a022a84b5`.
- Implementation coordinator: `maison-mol-1h4n`.
- Documentation reconciliation: `maison-mol-28r8`.
- Validation: `maison-mol-dgzm`.
- Holistic delivery review: `maison-mol-4i8o`.
- Documentation drift review: `maison-mol-u34v`.
- Delivery action: `maison-mol-p71j`, pending explicit selection.
