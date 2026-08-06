# Task reference

All commands operate on the selected consumer repository. Set `MAISON_CONSUMER_ROOT` or run from the consumer
checkout. The consumer must own `flake.nix`, `flake.lock`, and `inventory.toml`; Maison's checkout is never an implicit
configuration root.

## Aggregate commands

| Task                                     | Behavior                                                            |
|------------------------------------------|---------------------------------------------------------------------|
| `doctor`                                 | Diagnose the consumer's two ownership layers without mutation       |
| `consumer validate [--consumer PATH]`    | Validate consumer contracts without activation or provider access   |
| `plan [--host HOST] [--force-dotfiles]`  | Preview consumer system state, then render the read-only user plan  |
| `apply [--host HOST] [--force-dotfiles]` | Apply consumer Nix state, then converge consumer user state         |
| `update [INPUT] [--check]`               | Update only the consumer `flake.lock`; optionally validate          |
| `self:update`                            | Transactionally upgrade Maison from the consumer lock               |
| `deploy HOST`                            | Deploy the consumer's Linux system profile and user state           |
| `rollback`                               | Roll back only the active Nix system generation                     |
| `bootstrap [--consumer PATH]`            | Verify Maison runtimes, select a consumer, and converge both layers |
| `check`                                  | Validate Maison framework data, scripts, tests, and Nix outputs     |

## Hidden integration-test tasks

The following tasks are intentionally absent from the public `maison` command surface. Use direct Mise invocation
from the Maison checkout; `mise tasks --hidden` is the only supported discovery path for hidden tasks.

| Task                   | Behavior                                                                                    |
|------------------------|---------------------------------------------------------------------------------------------|
| `test:lume:install`    | Install the verified Trycua Lume 0.5.1 host prerequisite on Apple Silicon macOS 13 or newer |
| `test:bootstrap:linux` | Run the disposable Linux consumer bootstrap integration test                                |
| `test:bootstrap:mac`   | Run the disposable Lume macOS consumer bootstrap integration test                           |
| `test:deploy`          | Run the disposable Linux deployment integration test                                        |
| `test:image`           | Build or inspect the disposable Linux integration image                                     |

The Lume task installs the verified launcher at `${XDG_DATA_HOME:-$HOME/.local/share}/maison/lume/0.5.1/lume`
with its adjacent archive-provided `lume.app` bundle after verifying the pinned SHA-256
`7f10cfbe66a800f98a5db88129f7dc024600fcdc139e0be124845bc7a3dc1359`. It is idempotent and concurrency safe, does
not use the upstream shell installer, and is never invoked by public bootstrap, apply, deploy, or update
commands. The macOS image and worker lifecycle remain separate disposable test infrastructure.

### Linux integration task contracts

| Task                   | Arguments and contract                                                                |
|------------------------|---------------------------------------------------------------------------------------|
| `test:bootstrap:linux` | Optional host name, `--consumer PATH`, and `--dev`; runs disposable Linux convergence |
| `test:deploy`          | `--consumer PATH`; deploys Linux through the disposable container                     |
| `test:image`           | No consumer input; builds or reuses the pinned Apple Container image                  |

These tasks require an explicit external consumer root, a clean committed checkout, and direct hidden Mise
invocation. The bootstrap lane verifies the locked Maison GitHub revision and `bootstrap.sh` blob before running the
public bootstrap script. The deployment lane generates an ephemeral SSH key pair, transfers only its public half, and
uses verified mise, Lix, and Homebrew installer files; it never mounts or copies a host private-key directory or pipes
a network response into a shell. All disposable containers, stages, tokens, scripts, and keys are removed on every
exit path. The known `system-manager` builder failure remains external validation evidence when reproduced.

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

Authoring commands require a Git checkout of the consumer and reject dirty mutation targets. `plan`, `user:status`,
`list`, `validate`, and `search` remain read-only. Deployed snapshots without `.git` reject source mutations and point
back to the consumer authoring checkout.

`consumer validate` is read-only and runs the Maison-owned consumer contract. It checks the consumer flake and lock,
inventory, supported systems, package and dotfile declarations, fnox references, documentation links, and raw
credential/private-key boundaries. It performs check-only Nix evaluation and never invokes fnox or activates a system.

`user:plan` and `user:apply` share one command plan. Plan renders dry-run variants; apply performs trust, package, dotfile,
lock-link, and finalization steps. Forced dotfile replacement creates an exact manifest-backed backup before mutation.

Hidden `nix:*` tasks are compatibility aliases for `system:*` tasks.

## Verified bootstrap artifacts

Bootstrap metadata is checked in at `bootstrap/artifacts.toml`. Maison verifies each selected mise or Lix artifact before
installation. Runtime code comes from Maison; configuration and lock mutations are always rooted in the consumer.

When remote user convergence fails, deployment restores the prior consumer revision before restricted recovery. Recovery
repairs reversible user state without package/application convergence and writes a mode-0600 diagnostic under
`~/.local/state/maison/recovery/`.
