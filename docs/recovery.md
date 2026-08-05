# Recovery

## Bootstrap verification recovery

Bootstrap verification metadata lives in `bootstrap/artifacts.toml`. If a mise or Lix artifact fails verification, do
not execute it manually. Retry once; if it still fails, inspect the URL and checksum, then rerun with the reviewed pinned
artifact.

## Consumer selection recovery

The consumer repository is the execution and lock root:

```bash
export MAISON_HOME="$HOME/.maison"
export MAISON_CONSUMER_ROOT="$HOME/src/terroir"
maison doctor
```

The consumer must contain `flake.nix`, `flake.lock`, and `inventory.toml`. If it is unavailable, restore that Git checkout
or set `MAISON_CONSUMER_ROOT` to another reviewed checkout. Never copy private inventory or deploy endpoints into Maison
as a recovery shortcut; secrets and private keys remain in the consumer's fnox-selected provider.

## System rollback

```bash
maison system history
maison system rollback
```

On Darwin, the task prefers `darwin-rebuild switch --rollback` and does not move the profile first. On Linux, it rolls
back `/nix/var/nix/profiles/system-manager-profiles/system-manager` and activates the selected profile's `bin/activate`.

## Failed aggregate apply

`maison apply` runs consumer system state first. A system failure prevents user convergence. A later user failure leaves
the successfully activated system generation in place:

```bash
maison user status
maison user plan
maison user apply
```

## Rejected authoring command in a deployed snapshot

A deployed snapshot contains `.maison-revision` without `.git`. It can run runtime commands such as plan, apply, status,
deployment finalization, and recovery, but Maison rejects repository-writing commands there because the next deployment
will overwrite local source edits. Retry from the consumer Git checkout.

## Failed local repository mutation

Local authoring mutations store untracked lock and journal state under:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/maison/repository-mutations/
```

Each state directory is keyed by the canonical consumer path and uses owner-only permissions because journals can copy
consumer data. If a mutation is interrupted, the next mutation for that consumer acquires the lock, recovers incomplete
journals, and only then reads repository state. If recovery fails, Maison preserves the journal, original copies, candidate
copies, and diagnostics. Do not delete the journal directory until the consumer files and preserved copies are understood.

## Failed user apply

Default `maison user plan` and `maison user apply` do not force replacement of whole-file conflicts. To preview and then
perform the same forced handoff:

```bash
maison user plan --force-dotfiles
maison user apply --force-dotfiles
```

The forced plan is read-only. The forced apply backs up exact targets mise refused before replacement. Backups live under
`~/.local/state/maison/backups/dotfiles/<timestamp>` and contain a manifest; inspect it before restoring:

```bash
maison user restore-dotfiles ~/.local/state/maison/backups/dotfiles/<timestamp> --force
```

Restore refuses paths outside Maison's backup root, malformed or escaping manifest entries, and missing payloads. It stops
at the first failure and can be retried for entries still marked `pending`.

Before package convergence on macOS, Maison archives live application bundles in the backup tree with `ditto`, verifies the
ZIP, unregisters the bundle, and removes the original only after verification. Docker Desktop compatibility handling is
limited to the documented exact completion-link and cask cases; unrelated installer failures remain errors.

## Failed remote user deployment

Deployment archives only committed consumer content and keeps repository transaction state in a root-owned same-filesystem
namespace outside the managed user's writable home. The deployment account uses command-scoped sudo elevation.

When consumer user convergence fails, deployment verifies and restores the prior consumer revision before running
restricted recovery as the managed user. Recovery repairs reversible dotfiles, mise lock links, non-package mise state,
and finalization. It does not rerun package/application convergence, application-backup migration, system activation, or
Nix rollback. An explicit `--force-dotfiles` choice is preserved; recovery never enables it implicitly.

Recovery writes `remote-convergence-<failed-revision>.json` under `~/.local/state/maison/recovery/` with failed/restored
revisions, exit statuses, completed steps, and package/application side effects. The original convergence failure remains
the deployment exit status. If rollback or transaction cleanup fails, inspect the journal, staging tree, rollback tree, and
lock before making changes.

On startup, Maison runs incomplete-transaction recovery before user convergence.

## Failed system deployment

The user phase does not start until the system phase succeeds. Linux activation requires systemd and verifies hostname,
timezone/localtime, SSH configuration/reload, and Maison-managed service units. With `auto_rollback` and
`magic_rollback` enabled, deploy-rs attempts to restore the prior system profile after activation failure or lost
confirmation connectivity.

## nix-darwin adoption files

The one-time Darwin preflight may preserve unmanaged files as:

```text
/etc/nix/nix.conf.before-nix-darwin
/etc/nix/nix.custom.conf.before-nix-darwin
```

Retain them until several successful switches have completed.

## Failed repository transition

If a repository migration or remote publication fails, keep the consumer staging checkout, the approved owner-only
manifest, and the original historical source intact. Do not make the old source public, delete it, or remove local backups
as a recovery step. Re-run privacy, consumer-boundary, fresh-history, and remote-state checks before any archive
transition. Secrets and private keys are never recovered from Git.

## Broken shell

Use `/bin/zsh` or `/bin/bash`, ensure `~/.local/bin` is on `PATH`, and inspect `~/.zshrc` plus `~/.config/maison/zsh`.
The shell is user-owned, so repairing it does not require rebuilding the Nix system closure.
