# Design — Overlay authoring lifecycle and command surface

## Metadata

- Beads feature root: `maison-mol-3jb`
- Feature slug: `maison-overlay-authoring-lifecycle`
- Design path: `docs/src/features/maison-overlay-authoring-lifecycle/design.md`
- Implemented record: `docs/src/features/maison-overlay-authoring-lifecycle/index.md`
- Base branch: `main`
- Status: delivered

## Feature Summary

Make the private overlay a safe, inspectable, and publishable authoring repository. Maison will expose top-level
`status` and `publish` commands, refresh the overlay before software mutations, and create focused Git commits for
successful tool, package, and application additions or removals. The existing help output will flatten the workflow
commands without implying a nonexistent `workflow` command.

## User Intent

Maison's workflow commands are top-level commands, not children of a `workflow` command. The help output should present
those commands directly while preserving the existing grouped help for `github`, `app`, `package`, `tool`, `host`,
`system`, `user`, and `docs`.

The private overlay should also behave like a small authoring repository: the operator can inspect whether it is clean,
published, ahead, behind, diverged, or offline; explicitly publish committed changes; and trust add/remove commands to
refresh from the remote and commit only their successful declaration changes. The public Maison checkout must never be
the fallback target for these personal software mutations.

## Goals

- Flatten only the `workflow` heading in Maison's top-level help and add `status` and `publish` to the top-level command
  surface.
- Add overlay-only `maison status` and `maison publish` commands using the active saved/environment-selected overlay.
- Fetch remote refs for status when possible and clearly report when remote comparison is unavailable or based on the
  last known tracking ref.
- Refresh the active overlay with a fast-forward-only pull before `tool`, `package`, and `app` add/remove mutations.
- Automatically commit successful add/remove declarations with focused, predictable messages.
- Preserve unrelated changes, staged state, untracked files, and ignored files without accidentally committing or
  deleting them.
- Keep publication explicit; add/remove commands never push to a remote.

## Non-Goals

- Automatically publishing, creating, or configuring a remote overlay repository.
- Running the full `maison sync` workflow before authoring a mutation; that command still pulls both repositories and
  applies configuration.
- Automatically committing arbitrary overlay edits or changes in the public Maison checkout.
- Automatically rolling back installed packages or applications when Git commit creation fails.
- Changing `host:add`, update commands, inventory ownership, or the public starter configuration behavior outside the
  software add/remove commands covered here.
- Adding a separate overlay argument to `status` or `publish`; both use the active resolved overlay.

## User-Facing Behavior

### Help output

The help heading remains:

```text
Available commands and their subcommands:

apply             Apply the Nix system layer, then converge the mise user layer
bootstrap         Install/repair Nix, apply system configuration, and converge user state
deploy            Deploy Linux system state, then transactionally converge its mise user environment
doctor            Diagnose the Nix system and mise user layers without changing them
fix               Apply deterministic repository fixes
plan              Preview the Nix system layer, then the mise user layer
rollback          Roll back only the Nix system layer
status            Show the active overlay and remote status
sync              Pull Maison and your private overlay, then apply both layers
update            Update Nix inputs transactionally

github:
  auth            Configure GitHub authentication for Maison, mise, and Nix
```

Only the `workflow:` label is removed. Existing non-workflow groups remain in their current order and format.

### `maison status`

`status` inspects the active overlay resolved from existing overlay state/environment behavior. It accepts no separate
overlay path. It reports the overlay path, branch/upstream, worktree state, and the relationship to the upstream:

- clean and in sync;
- uncommitted tracked or untracked changes;
- committed changes ahead of the remote;
- remote changes ahead of the checkout;
- diverged history; or
- no configured upstream/remote.

The command fetches the configured remote when possible. If fetching is unavailable because the device is offline or
credentials/network access fail, it reports that the remote comparison is unavailable and identifies the last-known
tracking state instead of claiming that the repository is in sync. Any inspectable state is reported with exit status
zero; no valid active overlay or repository is an error.

### `maison publish`

`publish` uses the active overlay's configured upstream branch and never chooses a remote or branch implicitly. It:

1. fetches the upstream before changing the worktree;
2. fails without stashing if the upstream is unavailable, no upstream is configured, or local and remote history is not
   a fast-forward-publishable relationship;
3. temporarily stashes tracked and untracked changes, but never ignored files;
4. pushes already-committed local changes;
5. restores the stash after a successful or failed push; and
6. leaves the stash intact and returns non-zero if restoration conflicts.

It does not create a commit for arbitrary local edits. A successful no-op when there are no commits to push is allowed and
is reported clearly.

### Configuration scope

The authoring lifecycle preserves the existing configuration scope. Common tool and package declarations belong in
`config/mise/config.toml`; platform-specific resolution remains in the corresponding mise lock/config files. The
`--macos` package option selects `config/mise/config.macos-arm64.toml`, while application commands use their existing
Apple Silicon application config. Inventory profiles (`base`, `dev`, `mac`, and `linux`) select Nix modules; Maison does
not add a separate mise profile selector or a profile argument to these authoring commands.

### Add/remove mutation lifecycle

`tool:add`, `tool:remove`, `package:add`, `package:remove`, `app:add`, and `app:remove` require an active private overlay
and a Git authoring checkout. They fail instead of falling back to public `config/mise` files. The target overlay must
have a configured upstream that can be fast-forward-pulled; an unavailable remote, missing upstream, or diverged history
stops the command before the declaration is edited.

After acquiring the existing repository mutation lock, the command stashes tracked and untracked changes (never ignored
files), pulls the overlay with fast-forward-only semantics, and restores the stash. A restoration conflict aborts the
mutation. Any transaction target file that already contains local changes after restoration is rejected; unrelated dirty
files in other paths remain allowed and are not included in the generated commit.

The existing candidate-install/validate/replace transaction remains authoritative. Its journal is completed before Git
commit creation so a commit identity, hook, or subprocess failure is a post-transaction error: validated declaration
changes remain in place and the command prints manual recovery guidance. Only after the transaction completes does Maison
create a Git commit containing the changed declaration and any generated lockfile. Generated subjects use literal
backticks and the effective identifier:

```text
added(tool): `github:owner/tool@version`
removed(package): `brew:git`
added(app): `ghostty`
```

The `package` category is used for `package --macos`; the tool/package/app command's effective identifier is used,
including its manager/cask and requested version where applicable. A Git commit failure leaves the validated declaration
changes in place, reports the manual-commit recovery path, and does not pretend that installation side effects were
rolled back. Add/remove commands never push these commits.

## Requirements

### Functional Requirements

- The CLI registers top-level `status` and `publish` tasks and dispatches their task-specific help normally.
- Help renders workflow tasks without a `workflow:` heading while retaining all other current groups.
- Status uses only the active saved/environment-selected overlay and does not inspect an arbitrary path.
- Status attempts a remote fetch, reports last-known comparison state when the fetch is unavailable, and distinguishes
  dirty, ahead, behind, diverged, in-sync, and no-upstream states.
- Publish uses the configured upstream, fetches before stashing, refuses non-publishable history, preserves tracked and
  untracked local changes, leaves ignored files untouched, and reports stash restoration conflicts without dropping the
  stash.
- Covered software add/remove commands require a private overlay, refresh it before editing, reject target files that
  already contain local changes, and never invoke full `maison sync` as their refresh path.
- Successful covered mutations commit only operation target paths after the existing transaction succeeds, with the
  exact `added(scope): \`identifier\`` or `removed(scope): \`identifier\`` subject contract.
- Commit failures preserve the successful file mutation and provide actionable recovery output.

### Quality Requirements

- Reuse the existing XDG overlay state, authoring-checkout guard, fail-fast repository lock, mutation journals, and
  candidate validation instead of creating parallel ownership or transaction systems.
- Use argument arrays or equivalent safe subprocess APIs for Git paths, refs, and commit identifiers; do not evaluate
  overlay paths, branch names, or package names as shell code.
- Preserve unrelated worktree/index state and never silently delete an untracked or ignored file.
- Keep status/publish and pure overlay Git behavior independently testable without Pi, TUI, Nix activation, package
  installation, or network access to a real remote.
- Provide actionable diagnostics for missing overlays, missing upstreams, stale/offline status, divergent history,
  failed pulls/pushes, target-file dirtiness, commit-hook/identity failures, and stash conflicts.

### Compatibility and Migration Requirements

- Existing overlay source precedence and saved overlay state remain unchanged.
- Existing `maison sync` continues to pull Maison and the overlay and then apply both layers.
- Existing user-facing command names, including `maison user status`, remain available.
- Public Maison's neutral fallback files remain available to read-only/apply workflows, but covered software authoring
  commands no longer mutate them when no private overlay is active.
- Existing transaction rollback/journal behavior remains in force for candidate edits and lockfile replacements.

## Existing Context

The CLI in `bin/maison` discovers executable `.mise/tasks` and formats tasks into a `workflow` group plus other
namespace groups. `scripts/maison_overlay.py` owns overlay source precedence, XDG state, local paths, and remote clone
updates. `.mise/lib/overlay.sh` exports the active overlay and currently falls back to the public repository when no
overlay is present.

The software authoring tasks already use `.mise/lib/transaction.sh`, `.mise/lib/repository_mutation.py`, parser-backed
TOML edits, candidate validation, a repository lock, and mutation journals. `tool:add`/`remove`, `package:add`/`remove`,
and `app:add`/`remove` currently replace files transactionally but do not create Git commits. `sync` currently performs
full repository pulls followed by `apply`, so it is not a safe pre-authoring refresh primitive.

The completed overlay bootstrap feature established the private overlay boundary, direct local Git paths, the XDG
saved-state contract, and the Copier-generated overlay layout. This feature extends that boundary for authoring without
moving private data or secrets into public Maison.

## Proposed Design

### Shared overlay Git operations

Extend or factor the existing stdlib overlay helper so shell tasks can invoke one consistent, pure/testable
implementation for:

- resolving and requiring an active private Git overlay without changing the public fallback used by read-only or
  convergence workflows;
- fetching/updating status against the configured upstream and distinguishing fresh versus last-known comparison;
- temporary stash/pull/restore handling with tracked plus untracked files and no ignored files;
- fast-forward/upstream relationship checks before any publish stash;
- focused commit creation using an explicit path list and a temporary Git index or equivalent path-limited mechanism that
  does not commit unrelated staged or worktree changes; and
- returning structured outcomes/errors so shell tasks own only user-facing wording.

All Git subprocesses receive paths and refs as separate arguments. The helper must not invoke full `maison sync`, and it
must leave the existing repository mutation journal/lock as the transaction boundary for file edits.

### Mutation integration

The covered mutation tasks continue to acquire the target repository lock before reading mutable files. Once inside the
lock, they require an active overlay, refresh it with the shared helper, verify target paths are clean, and then execute
the existing candidate transaction. The task records the exact declaration/lock paths it changed and marks the
transaction successful and complete before invoking the focused commit helper. A commit error is a post-transaction
failure with preserved files, not a request to reverse external installation effects. The helper receives explicit target
paths and the effective identifier so each task does not duplicate Git state handling.

The target cleanliness check is path-specific: unrelated files may remain dirty, but a pre-existing change in a config or
lockfile that the operation would commit is rejected. The temporary-index commit preserves unrelated staged files and
only records the operation paths.

### Command tasks and help

Add `.mise/tasks/status` and `.mise/tasks/publish` as top-level tasks. `status` remains inspection-oriented and does not
change declarations. `publish` takes the overlay repository lock because stash/push/restore changes repository state;
it does not invoke configuration convergence. Update `bin/maison`'s workflow formatter to print workflow rows directly,
then leave existing non-workflow grouping logic intact.

## Architecture Consistency

### Existing Patterns Reused

- `scripts/maison_overlay.py` and `.mise/lib/overlay.sh` for active-overlay resolution and XDG state.
- `.mise/lib/repository_mutation.py` for authoring checks, lock ownership, recovery, and private state directories.
- `.mise/lib/transaction.sh` for candidate replacement, journals, rollback, and signal handling.
- Parser-backed `config_edit.py` edits and existing mutation task boundaries.
- `bin/maison`'s task discovery and generated task-specific help.

### Invariants Preserved

- Public Maison owns reusable framework and neutral policy; private overlay owns personal/site software declarations.
- A covered add/remove command never writes public fallback configuration.
- Successful external installation is followed by a validated declaration and focused Git commit; failed candidate
  transactions never create the commit.
- Unrelated local work and ignored files are not committed or deleted.
- Publishing is explicit and never occurs as a side effect of mutation.
- System/user activation and the Nix ownership boundary are unchanged.

### New Decisions Introduced

- `maison status` and `maison publish` are top-level commands using the active overlay only.
- Remote refresh is required before covered add/remove authoring; offline or divergent overlays fail safe.
- Auto-generated mutation subjects are `added(scope): \`identifier\`` and `removed(scope): \`identifier\``.
- Commit failure preserves the already-successful declaration mutation and reports manual recovery.
- Status may fetch; when it cannot, it reports that the comparison is last-known rather than claiming synchronization.

### Architecture Documentation Changes

Update architecture and operations/reference pages to describe the overlay authoring boundary, refresh/publish lifecycle,
focused commits, no-public-fallback rule, stale/offline status wording, and commit-failure recovery.

## Operational Considerations

Operators should run `maison status` before authoring or `maison publish` when they need to inspect the overlay. Software
add/remove commands may contact the configured remote and can fail offline by design. Local unrelated work is preserved
through the refresh; target-file edits must be committed or stashed manually before retrying.

`maison publish` does not publish uncommitted edits. If a push fails, the temporary stash is restored. If restoration
conflicts, the stash remains available for explicit recovery. A failed auto-commit leaves the declaration changes in the
overlay, so operators should inspect `maison status` and create the documented commit manually.

## Documentation Impact

| Documentation concern          | Exact page                                                           | Create or update        | Planned change                                                                                                                                               | Owning Beads task  |
|--------------------------------|----------------------------------------------------------------------|-------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------|
| Introduction / command surface | `README.md`                                                          | Update                  | Add top-level status/publish usage, overlay-only authoring, commit/publish lifecycle, exact help semantics, and the preserved configuration/profile boundary | `maison-mol-0tm.3` |
| Architecture                   | `docs/architecture.md`                                               | Update                  | Document overlay authoring ownership, remote refresh, focused commits, and no-public-fallback invariant                                                      | `maison-mol-0tm.2` |
| Operations                     | `docs/operations.md`                                                 | Update                  | Document status states, offline reporting, publish stash/push/restore behavior, and recovery                                                                 | `maison-mol-0tm.1` |
| Reference                      | `docs/task-reference.md`                                             | Update                  | Add status/publish contracts and revised software mutation guarantees                                                                                        | `maison-mol-0tm.3` |
| Reference                      | `docs/src/reference/tooling.md`                                      | Update                  | Document overlay status/publish commands, mutation commit behavior, and configuration/profile scope                                                          | `maison-mol-0tm.3` |
| Package/application authoring  | `docs/package-policy.md`, `docs/add-a-tool.md`, `docs/add-an-app.md` | Update                  | Explain overlay requirement, pre-mutation refresh, target cleanliness, and generated commit subjects                                                         | `maison-mol-0tm.2` |
| Navigation                     | `docs/src/SUMMARY.md`                                                | Update                  | Register this feature design; no new reader page is required                                                                                                 | Planning/close-out |
| Roadmap                        | `docs/src/planned-features.md`                                       | Update                  | Add this feature with dependency/status narrative                                                                                                            | `maison-mol-0tm.3` |
| Implemented feature record     | `docs/src/features/maison-overlay-authoring-lifecycle/index.md`      | Create during close-out | Preserve delivery and audit evidence                                                                                                                         | Close-out          |

No new durable reader-facing page is required; existing operations, architecture, tooling, and authoring pages own these
questions.

## Validation Strategy

- Add behavior-first tests for CLI help flattening, task discovery, status states, offline/last-known reporting, publish
  upstream checks, stash preservation, push failure restoration, and restoration-conflict safety.
- Use temporary local Git repositories/bare remotes and controlled subprocesses; do not access a real remote or run real
  package installation, Nix activation, or system convergence.
- Add mutation tests for missing overlay refusal, pre-mutation fast-forward pull, offline/divergent refusal, target-file
  dirtiness, preservation of unrelated files/index entries, exact add/remove commit subjects, lockfile inclusion, commit
  failure preservation, and no commit after candidate/installation failure.
- Run focused Python unittest modules, shell syntax/static checks, documentation validation, mdBook, and the full
  repository check after implementation and review fixes stabilize.

## Implementation Decomposition

- **Overlay Git lifecycle and commands** — add shared status/publish/refresh/stash/upstream behavior and focused tests.
- **Transactional overlay mutation commits** — require active overlays, integrate refresh and target checks, and commit
  successful tool/package/app add/remove operations with focused tests.
- **Command surface and reader documentation** — flatten help, register top-level commands, update exact reader pages,
  roadmap, and contract tests.

## Dependencies and Parallelism

All implementation tasks depend on specification reconciliation. The mutation task depends on the shared Git lifecycle
contract/task because it uses refresh, stash, upstream, and focused-commit primitives. Command-surface documentation and
help tests depend on the final command behavior and mutation contract. Full validation follows all three slices.

## Rollout and Migration

The feature is additive for status/publish and changes only covered software authoring: users must have an active private
overlay and a reachable fast-forwardable upstream before add/remove. Existing public fallback files remain usable for
read-only and convergence behavior. Existing manually authored overlay changes are not auto-committed; only future
successful covered add/remove operations receive generated commits.

## Risks and Tradeoffs

- Requiring remote refresh makes authoring unavailable offline, but prevents new commits from being based on stale history;
  a future explicit offline mode can be designed separately.
- Temporary stashing is more complex than refusing all dirty worktrees, but permits unrelated work while protecting target
  files and untracked content.
- Preserving successful file changes after a Git commit failure can leave an uncommitted overlay, but reversing package
  and application side effects would be less safe and is outside the transaction boundary.
- A temporary-index/path-limited commit needs careful tests to avoid including unrelated staged work; target-file
  cleanliness is an additional safety precondition.

## Rejected Alternatives

- Keeping a visible `workflow:` help group when no `workflow` command exists.
- Calling full `maison sync` before authoring mutations, because it applies configuration and has a broader side effect.
- Committing arbitrary dirty overlay changes during `publish`.
- Silently mutating public Maison when no private overlay is active.
- Proceeding offline or through divergent history before a generated commit.
- Rolling back installed package/application side effects when Git commit creation fails.

## Open Questions

None.

## Deferred Decisions

None.

## Planning Record

### Questions Asked and Answers

- Automatic mutation commits may coexist with unrelated local changes, but only operation target paths may be committed.
- `maison publish` pushes existing commits, temporarily stashing tracked and untracked changes and restoring them; ignored
  files remain untouched.
- Covered add/remove operations fast-forward-pull only the active overlay before editing; they do not invoke full
  `maison sync`.
- Missing remotes, unreachable remotes, and divergent histories fail safely before authoring edits or publication.
- `maison status` fetches when possible and reports last-known comparison state when offline/unavailable; inspectable
  states exit zero.
- `publish` uses the configured upstream and refuses implicit remote/branch selection.
- Git commit failure preserves the successful mutation and reports recovery rather than rolling back installed effects.
- Only an active private overlay may receive these software mutations; public Maison is never the fallback target.
- Target config/lock files must be clean before a covered mutation; unrelated dirty paths are allowed.
- Commit subjects use literal backticks and the form `added(scope): \`identifier\`` or `removed(scope): \`identifier\``.
- Only the `workflow:` help heading is removed; all other groups remain as-is.

### Assumptions

- The active overlay is a Git authoring checkout with a configured upstream branch for covered add/remove operations.
- Existing generated overlays contain a usable initial commit and the normal overlay config/lock paths.
- Git's configured identity and hooks are the operator's responsibility; hook/identity failures are surfaced as post-
  transaction commit failures.
- "Effective identifier" means the command's manager-qualified package/cask/tool argument, including a requested tool
  version when the command supplied one.

### Design Changes During Planning

- The initial authoring behavior allowed public fallback files; the user explicitly changed covered software mutation to
  require an active private overlay.
- The initial publish concept became a fetch-first, upstream-only push with temporary stash preservation.
- Full `sync` was rejected as the pre-mutation refresh because it also applies system/user state.
- Same-file unrelated edits were made a refusal condition after distinguishing path-level commit safety from arbitrary
  worktree preservation.

### Source Material

- `bin/maison`
- `scripts/maison_overlay.py`
- `.mise/lib/overlay.sh`
- `.mise/lib/transaction.sh`
- `.mise/lib/repository_mutation.py`
- `.mise/tasks/tool/{add,remove}`
- `.mise/tasks/package/{add,remove}`
- `.mise/tasks/app/{add,remove}`
- `.mise/tasks/sync`
- `tests/test_repository_contracts.py`
- `tests/test_repository_mutation.py`
- `tests/test_transaction_behavior.py`
- `README.md`
- `docs/architecture.md`
- `docs/operations.md`
- `docs/task-reference.md`
- `docs/package-policy.md`
- `docs/add-a-tool.md`
- `docs/add-an-app.md`
- `docs/src/reference/tooling.md`
- `docs/src/features/maison-overlay-copier-bootstrap/design.md`
