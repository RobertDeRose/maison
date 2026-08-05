# Task reference

All commands operate on the selected consumer repository. Set `MAISON_CONSUMER_ROOT` or run from the consumer
checkout. The consumer must own `flake.nix`, `flake.lock`, and `inventory.toml`; Maison's checkout is never an implicit
configuration root.

## Aggregate commands

| Task                                                  | Behavior                                                            |
|-------------------------------------------------------|---------------------------------------------------------------------|
| `doctor`                                              | Diagnose the consumer's two ownership layers without mutation       |
| `plan [--host HOST] [--force-dotfiles]`               | Preview consumer system state, then render the read-only user plan  |
| `apply [--host HOST] [--force-dotfiles]`              | Apply consumer Nix state, then converge consumer user state         |
| `sync [--host HOST] [--user-only] [--force-dotfiles]` | Fast-forward the consumer repository, then run `apply`              |
| `update [INPUT] [--check]`                            | Update only the consumer `flake.lock`; optionally validate          |
| `status`                                              | Inspect the consumer worktree and upstream relationship             |
| `publish`                                             | Publish existing consumer commits through its configured upstream   |
| `deploy HOST`                                         | Deploy the consumer's Linux system profile and user state           |
| `rollback`                                            | Roll back only the active Nix system generation                     |
| `bootstrap [--consumer PATH]`                         | Verify Maison runtimes, select a consumer, and converge both layers |
| `check`                                               | Validate Maison framework data, scripts, tests, and Nix outputs     |

## System commands

| Task                 | Behavior                                                     |
|----------------------|--------------------------------------------------------------|
| `system:plan`        | Build the consumer system closure without activation         |
| `system:apply`       | Activate the consumer's Darwin or system-manager output      |
| `system:deploy`      | Deploy the consumer's Linux system profile through deploy-rs |
| `system:history`     | List canonical system-profile generations                    |
| `system:rollback`    | Select and activate the previous generation                  |
| `system:clean [AGE]` | Remove old system generations and collect the store          |

## User commands

| Task                                   | Behavior                                                        |
|----------------------------------------|-----------------------------------------------------------------|
| `user:plan [--force-dotfiles]`         | Render user convergence without invoking mutating commands      |
| `user:apply [--force-dotfiles]`        | Apply consumer dotfiles, packages, tools, apps, and preferences |
| `user:restore-dotfiles BACKUP --force` | Restore a manifest-backed Maison dotfile backup                 |
| `user:status`                          | Report consumer user-environment drift                          |
| `user:update`                          | Upgrade consumer mise-managed tools                             |
| `package:update`                       | Upgrade consumer Homebrew formulae                              |
| `app:update`                           | Upgrade consumer casks and Mac App Store apps                   |

## Consumer configuration commands

| Task                             | Behavior                                                             |
|----------------------------------|----------------------------------------------------------------------|
| `host:add`                       | Add a validated host to the consumer inventory and optional override |
| `host:list` / `host:validate`    | Read or validate the consumer inventory                              |
| `tool:add` / `tool:remove`       | Transactionally edit and focused-commit consumer tool config/lock    |
| `package:add` / `package:remove` | Transactionally edit and focused-commit consumer package config      |
| `package:search`                 | Search package sources without repository mutation                   |
| `app:add` / `app:remove`         | Transactionally edit and focused-commit consumer cask config         |
| `docs:build` / `docs:serve`      | Build or serve the Maison contributor book                           |

Authoring commands require a Git checkout of the consumer and reject dirty mutation targets. `plan`, `status`, `list`,
`validate`, and `search` remain read-only. Deployed snapshots without `.git` reject source mutations and point back to
the consumer authoring checkout.

`user:plan` and `user:apply` share one command plan. Plan renders dry-run variants; apply performs trust, package, dotfile,
lock-link, and finalization steps. Forced dotfile replacement creates an exact manifest-backed backup before mutation.

Hidden `nix:*` tasks are compatibility aliases for `system:*` tasks.

## Verified bootstrap artifacts

Bootstrap metadata is checked in at `bootstrap/artifacts.toml`. Maison verifies each selected mise or Lix artifact before
installation. Runtime code comes from Maison; configuration and lock mutations are always rooted in the consumer.

When remote user convergence fails, deployment restores the prior consumer revision before restricted recovery. Recovery
repairs reversible user state without package/application convergence and writes a mode-0600 diagnostic under
`~/.local/state/maison/recovery/`.
