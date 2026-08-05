# Overlay authoring lifecycle and command surface

> Historical record: this alternate repository command surface is retired. Consumer Git history is now managed
> explicitly with Git; see [Migration Contract](../../migration-contract.md).

## Delivery Summary

- Beads feature root: `maison-mol-3jb`
- Status: delivered, later retired by `maison-hi8`
- Pull request: not created (direct fast-forward merge)
- Merge commit: `dc385400c78c80f81bd7cd9b31b20c629b86fc6d` (fast-forward into `main`)
- Design record: [design.md](design.md)

## Delivered Capability

Maison now treats the active private overlay as a safe, inspectable authoring repository. Top-level `maison status`
reports worktree and upstream state, including stale or last-known remote comparisons, while `maison publish` fetches,
checks the configured upstream, pushes existing commits, and restores local tracked and untracked work without touching
ignored files. Neither command changes public Maison fallback files or creates arbitrary commits.

Software add/remove commands for tools, packages, and applications now require a private Git overlay. They refresh it
fast-forward-only before editing, reject dirty declaration or lock targets, preserve unrelated work, and create focused
commits only after successful declaration transactions. Commit failures preserve validated changes and provide manual
recovery guidance.

## User-Facing Behavior

```bash
maison status
maison publish
maison tool add github:owner/tool latest
maison package add brew:tool --macos
maison app remove ghostty
```

Help prints workflow commands directly beneath `Available commands and their subcommands:`; it retains the existing
`github`, `app`, `package`, `tool`, `host`, `system`, `user`, and `docs` groups. `maison status` reports clean, dirty,
ahead, behind, diverged, no-upstream, and offline/last-known states. `maison publish` never selects an implicit remote or
branch, stashes tracked and untracked files only, and leaves a recoverable stash when restoration conflicts.

Generated mutation subjects use literal backticks and the effective identifier, for example
`added(tool): \`github:owner/tool@version\`` or `removed(package): \`brew:git\``. Common declarations remain in
`config/mise/config.toml`; `package --macos` selects the Apple Silicon mise configuration, application commands use the
Apple Silicon application configuration, and inventory profiles select Nix modules rather than a mise profile selector.

## Design Integration

The implementation reuses Maison's saved/environment-selected overlay resolution, private authoring-checkout guard,
repository mutation lock, mutation journal, parser-backed TOML edits, candidate validation, and user-convergence
fallback behavior. The shared overlay Git helper keeps Git paths and refs argument-safe and independently testable.
Transaction journals complete before focused commits are attempted, so Git identity or hook failures are post-transaction
errors rather than unsafe rollback requests.

The public repository remains the framework and neutral fallback for read-only and convergence paths. Covered software
mutations never write that fallback, and publication remains an explicit operation separate from `maison sync`.

## Operational Impact

Operators can inspect the overlay before authoring or publishing with `maison status`. Covered add/remove commands may
contact the configured upstream and fail safely when it is unavailable, missing, or divergent. Unrelated local work is
preserved through refresh and publication; declaration or lock targets must be clean before retrying.

A failed generated commit does not roll back an already-successful package or application installation. Inspect the
validated overlay changes, run `maison status`, and create the documented focused commit manually. A failed push restores
the temporary stash; a restoration conflict leaves that stash available for explicit recovery.

## Reference and Contracts

- [Architecture](../../architecture.md)
- [Operations](../../operations.md)
- [Task reference](../../task-reference.md)
- [Tooling reference](../../reference/tooling.md)
- [Package policy](../../package-policy.md)
- [Adding a tool](../../add-a-tool.md)
- [Adding an app](../../add-an-app.md)
- [Feature design](design.md)

## Validation Evidence

- `python3 -m unittest -v tests.test_repository_contracts tests.test_overlay_git tests.test_transaction_behavior` — passed (54 focused tests).
- `bash -n bin/maison` and `shellcheck -x bin/maison` — passed.
- `uv run scripts/check-docs.py` — passed.
- `rumdl check` on all changed reader-facing Markdown pages — passed.
- `mise run check` — passed: 199 tests plus Nix, documentation, shell, Python, type, formatting, and hook checks.
- Temporary local Git repositories covered status, refresh, publication, stash recovery, target cleanliness, focused
  commits, no-overlay refusal, and commit-failure preservation; no real remote publication or system activation was run.

## Design Reconciliation

### Delivered as Designed

- Flattened only the nonexistent `workflow:` help heading and added top-level `status` and `publish` commands.
- Added active-overlay status with fresh or last-known remote comparison and safe publish stash/push/restore behavior.
- Added fast-forward-only pre-mutation refresh and private-overlay-only software authoring.
- Added path-specific target cleanliness checks and focused `added`/`removed` commits after transaction completion.
- Preserved unrelated work, ignored files, public read-only/convergence fallback, and existing `maison sync` semantics.
- Documented configuration scope, inventory profile ownership, recovery, and offline behavior.

### Intentional Changes

- Covered software add/remove operations now refuse public fallback mutation when no private Git overlay is active.
- Git commit failures preserve validated declaration changes instead of attempting to reverse external installation effects.
- The command surface exposes status and publish directly while retaining namespace grouping for all other command families.

### Deferred Work

- Pull-request creation was not performed; this feature uses the explicitly requested direct fast-forward merge.
- Real remote, package installation, Nix activation, and host deployment remain outside the deterministic validation environment.
- Creating or configuring a private remote repository remains an operator-controlled action.

### Rejected or Removed Scope

- No automatic publication, arbitrary-edit commits, implicit remote selection, or full `maison sync` refresh was added.
- No public Maison mutation fallback, separate status/publish overlay argument, or mise profile selector was introduced.
- No host authoring, inventory ownership, bootstrap, Nix ownership, or supported-platform boundary was changed.

## Documentation Updated

- `README.md`
- `docs/architecture.md`
- `docs/operations.md`
- `docs/task-reference.md`
- `docs/src/reference/tooling.md`
- `docs/package-policy.md`
- `docs/add-a-tool.md`
- `docs/add-an-app.md`
- `docs/src/planned-features.md`
- `docs/src/features/index.md`
- `docs/src/SUMMARY.md`
- `docs/src/features/maison-overlay-authoring-lifecycle/design.md`
- `docs/src/features/maison-overlay-authoring-lifecycle/index.md`

## Audit Trail

- Specification reconciliation: `maison-mol-43o`, commit `db23f2165d58e830223eb2d497b2d7f084ef294b`.
- Shared overlay Git lifecycle and commands: `maison-mol-0tm.1`, commit `d2e7b151a31c0ad6e88a0c8a8632007c944d086a`.
- Transactional software mutation integration: `maison-mol-0tm.2`, commit `7c75189f4c7578e82a7b209ddcae67e0404de693`.
- Command surface and reader documentation: `maison-mol-0tm.3`, commit `10b467bcc04aea38d6dde41f9a9d54d8eada8cb6`.
- Implementation coordinator: `maison-mol-0tm`.
- Documentation reconciliation: `maison-mol-9xx`.
- Validation: `maison-mol-cm8`.
- Holistic delivery review: `maison-mol-86a`.
- Documentation drift review: `maison-mol-70j`.
- Delivery action: `maison-mol-dv6`, direct fast-forward merge into `main` at
  `dc385400c78c80f81bd7cd9b31b20c629b86fc6d`.
