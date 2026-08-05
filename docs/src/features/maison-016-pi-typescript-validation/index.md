# MAISON-016: Pi TypeScript validation boundary

## Delivery Summary

- Beads feature root: `maison-mol-fmud`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

At delivery, Maison validated its Pi extensions through a repository-owned TypeScript workspace. The workspace pinned
the Pi API packages, TypeScript compiler, test runner, and Node type definitions without changing the files symlinked
into the user's Pi installation. The 983-line pager delegated pure Markdown parsing, key decoding, navigation, timer,
and terminal-layout behavior to testable modules.

After the Maison/Terroir ownership split, the Pi extension sources and validation workspace were relocated to the private
Terroir repository. Maison now retains only public Pi settings defaults and does not publish or validate personal
extensions.

## User-Facing Behavior

The historical delivery preserved Pi extension registration, command names, clipboard behavior, and pager rendering.
The relocated Terroir workspace retains direct validation with `npm ci --ignore-scripts --no-audit --no-fund`,
`npm run typecheck`, and `npm test`; those commands are no longer Maison tasks.

## Design Integration

The implementation keeps Nix/Lix as the privileged system layer and mise as the repository/user tooling layer. Actual
Pi package declarations supply the extension types, while the project-local npm lockfile supplies reproducible
validation dependencies. `pager/markdown.ts`, `pager/keys.ts`, and `pager/navigation.ts` do not import Pi, TUI,
clipboard, process, or terminal APIs. `pager.ts` remains the integration adapter for rendering and runtime events.

The scoped Node runtime exception is documented explicitly: global configuration serves standalone Pi, and the
repository configuration serves locked validation without replacing global user convergence.

## Operational Impact

Terroir contributors should run the pinned npm validation commands after changing Pi extensions and remove
`node_modules` afterward. Maison's public checks no longer install or traverse the private Pi workspace. No Pi or
OpenCode runtime configuration is changed by the validation metadata.

## Reference and Contracts

- [Architecture](../../architecture.md)
- [Developer tooling](../../development/tooling.md)
- [Tooling reference](../../reference/tooling.md)
- Pi contributor guidance: private Terroir `dotfiles/pi/AGENTS.md`
- OpenCode boundary: private Terroir `dotfiles/opencode/README.md`
- [Feature design](design.md)

## Validation Evidence

- Historical delivery evidence: `mise run check:typescript` passed with `tsc --noEmit` and 10 focused behavioral tests
  before the workspace moved to Terroir.
- Current Terroir evidence: `mise run check` and its GitHub validation workflow run the same typecheck and 10 focused
  behavioral tests from the private workspace.
- `uv run scripts/check-docs.py` — passed after documentation reconciliation.
- Historical delivery evidence: `shellcheck .mise/tasks/check/_default .mise/tasks/check/typescript` passed before the
  workspace moved to Terroir.
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

- Repository Node 24 was a scoped validation override while global configuration retained the standalone Pi runtime.
  The ownership test and architecture documentation described this boundary explicitly.
- The extension sources and validation workspace moved to private Terroir after the repository split; Maison's public
  framework no longer owns personal Pi behavior.
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
- Terroir `dotfiles/pi/AGENTS.md`
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
