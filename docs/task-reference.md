# Task reference

## Aggregate commands

| Task                                                  | Behavior                                                                                                                                                                                                                                                    |
|-------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `doctor`                                              | Diagnose both ownership layers without mutation                                                                                                                                                                                                             |
| `plan [--host host] [--force-dotfiles]`               | Preview the Nix system layer, then render the read-only user convergence plan; `--force-dotfiles` forwards after the system preview                                                                                                                         |
| `apply [--host host] [--force-dotfiles]`              | Apply Nix system state, then user convergence; the same force flag forwards to user apply and system failure stops the sequence                                                                                                                             |
| `sync [--host host] [--user-only] [--force-dotfiles]` | Pull Maison and the active overlay with fast-forward-only Git pulls, then run `apply`; a pull failure stops before apply                                                                                                                                    |
| `update [input] [--check]`                            | Update flake inputs atomically; optionally run full validation                                                                                                                                                                                              |
| `status`                                              | Inspect the active private overlay, worktree, upstream relationship, and fresh or last-known remote comparison                                                                                                                                              |
| `publish`                                             | Fetch and publish committed active-overlay changes through its configured upstream while preserving local work                                                                                                                                              |
| `deploy <host>`                                       | Deploy Linux system state using the configured deployment account (`maison-deploy` by default), then stage source through a root-owned repository transaction, converge remote user state, and run rollback-verified restricted recovery after user failure |
| `rollback`                                            | Roll back only the Nix system generation                                                                                                                                                                                                                    |
| `bootstrap [--overlay SOURCE]`                        | Store or refresh the private overlay source, verify pinned mise and Lix artifacts, install or repair Nix, then converge both layers system-first                                                                                                            |
| `check`                                               | Install repository `mise.toml` tools, validate data and scripts, run behavioral tests, and build Nix checks                                                                                                                                                 |

## System commands

| Task                 | Behavior                                            |
|----------------------|-----------------------------------------------------|
| `system:plan`        | `nh darwin build` or build a system-manager closure |
| `system:apply`       | `nh darwin switch` or system-manager switch         |
| `system:deploy`      | deploy-rs Linux system profile                      |
| `system:history`     | List canonical system-profile generations           |
| `system:rollback`    | Select and activate the previous generation         |
| `system:clean [age]` | Remove old system generations and collect the store |

## User commands

| Task                                               | Behavior                                                                                                                                                                       |
|----------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `user:plan [--force-dotfiles]`                     | Render the read-only user convergence command preview without invoking mise, package, dotfile, trust, or migration commands; force is opt-in and matches user apply            |
| `user:apply [--force-dotfiles]`                    | Sanitize live app backups, then apply dotfiles, packages, tools, apps, and preferences; explicitly forced conflicts receive exact manifest-backed snapshots before replacement |
| `user:restore-dotfiles <backup-directory> --force` | Restore pending entries from a Maison dotfile backup manifest; force is required to replace existing targets                                                                   |
| `user:status`                                      | Report user-environment drift                                                                                                                                                  |
| `user:update`                                      | Show outdated mise tools, then upgrade those tools                                                                                                                             |
| `package:update`                                   | Upgrade configured Homebrew formulae                                                                                                                                           |
| `app:update`                                       | Upgrade configured Homebrew casks and Mac App Store apps                                                                                                                       |

## Configuration commands

| Task                             | Behavior                                                                                                                                                        |
|----------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `host:add`                       | Authoring-only: add a host to the active public or overlay inventory through typed validation and parser-backed TOML edits                                      |
| `host:list` / `host:validate`    | Read or validate the active public or overlay inventory                                                                                                         |
| `tool:add` / `tool:remove`       | Authoring-only: require the private overlay, refresh it fast-forward-only, then transactionally edit and focused-commit tool configuration and locks            |
| `package:add` / `package:remove` | Authoring-only: require the private overlay, refresh it fast-forward-only, then transactionally edit and focused-commit common or platform package declarations |
| `package:search`                 | Search package sources without repository mutation                                                                                                              |
| `app:add` / `app:remove`         | Authoring-only: require the private overlay, refresh it fast-forward-only, then transactionally edit and focused-commit Apple Silicon macOS cask declarations   |
| `docs:build` / `docs:serve`      | Load the contributor environment and build or serve this book                                                                                                   |

`user:plan` and `user:apply` share one user-convergence command plan for the same flags. Plan renders the dry-run
variants for preparation, dotfiles, lock links, packages, and remaining mise user state without executing them. Apply
trusts the repository mise config, uses the package convergence helper, and runs user finalization; these execution-only
substitutions do not change force-dotfile semantics.

Hidden `nix:*` tasks are compatibility aliases to the corresponding `system:*` tasks and contain no separate activation logic.

Configuration mutation commands parse the complete target TOML before writing, preserve supported comments, quoted keys,
table boundaries, arrays of tables, and CRLF newlines, then validate the edited document before replacing the candidate
file. Malformed or unsupported TOML fails without partially rewriting the repository file.

Repository mutation commands that write checked-in or overlay repository files (`tool:add`, `tool:remove`, `package:add`,
`package:remove`, `app:add`, `app:remove`, `host:add`, and `update`) are authoring-only. They require a Git authoring
checkout for the target repository, acquire one fail-fast local lock, recover incomplete local journals, and then read
mutable state. A deployed snapshot has `.maison-revision` without `.git` and rejects these commands with guidance to use
the public source checkout or private overlay repository. Read-only commands such as plan, status, list, validate, and
search do not take the repository mutation lock or authoring checkout guard.

The covered software add/remove commands require an active private Git overlay and never mutate public fallback files.
They refresh the overlay fast-forward-only before reading target files, preserve unrelated tracked/untracked work without
touching ignored files, and reject a dirty declaration or lock target. Successful transactions create only focused
`added(scope): \`identifier\`` or `removed(scope): \`identifier\`` commits; Git commit failures preserve the validated
files and report manual recovery. `publish` never creates such commits for arbitrary edits.

## Overlay-aware behavior

`--overlay` is a bootstrap flag. After bootstrap, tasks read the saved overlay state from `${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml`. If the clone contains `inventory.toml`, inventory lookups, `host:add`, system planning, Nix evaluation, and deployment target selection use that overlay file and its sibling `hosts/` tree. Public starter files remain the fallback when no overlay inventory is present. Because `host:add` writes the active inventory repository, it checks the overlay clone for Git authoring evidence when an overlay inventory is active.

## Verified bootstrap artifacts

Bootstrap artifact metadata is checked in at `bootstrap/artifacts.toml`. Maison downloads the selected mise or Lix artifact to disk, verifies its SHA-256 digest for the current supported system, then executes or installs only that verified local file. The remote deployment mise fallback uses the same repository metadata.

When remote user convergence fails, `deploy` restores the prior repository before running its internal recovery task. The
recovery task repairs reversible user state without package/app convergence and writes a mode-0600 diagnostic under
`~/.local/state/maison/recovery/`; package/app side effects remain follow-up work.
