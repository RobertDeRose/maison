# Recovery

## Bootstrap verification recovery

Bootstrap verification metadata lives in `bootstrap/artifacts.toml`. If a mise or Lix artifact fails verification, do not execute it manually. Retry once to rule out a partial download; if it still fails, inspect the artifact URL and checksum in the manifest, update the manifest only after reviewing the upstream release, or manually install the pinned artifact after verifying the same SHA-256 digest.

For Lix installer failures after checksum verification, fix the reported Nix installer issue and rerun bootstrap. For mise failures after checksum verification, install the verified binary as `~/.local/bin/mise`, ensure it is executable, and rerun bootstrap.

## Overlay recovery

The supported repository pair is the public Maison framework plus a user-selected private overlay. The archived source
repository should be used only for migration recovery or historical rollback.

Maison's overlay selection is local state:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml
${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay
```

If setup cannot find the private overlay, rerun bootstrap with `--overlay GIT-URL-OR-PATH` or restore the
state file. If the clone is corrupt, move it aside and rerun bootstrap so Maison can clone it again. Do not put private
inventory, trusted keys, or real deploy endpoints into public Maison as a recovery shortcut.

## System rollback

```bash
maison system history
maison system rollback
```

On Darwin, the task prefers `darwin-rebuild switch --rollback` and does not move the profile first. On Linux, it rolls back `/nix/var/nix/profiles/system-manager-profiles/system-manager` and activates the selected profile's `bin/activate`.

## Failed aggregate apply

`maison apply` runs system state first. A system failure prevents user convergence. A later user failure leaves the successfully activated system generation in place:

```bash
maison user status
maison user plan
maison user apply
```

## Rejected authoring command in a deployed snapshot

A deployed snapshot contains `.maison-revision` without `.git`. It can run runtime commands such as plan, apply, status,
deployment finalization, and recovery, but Maison rejects repository-writing authoring commands there because the next
deployment will overwrite local source edits. Retry the command from the public Maison Git checkout, or from the private
overlay Git checkout when the command writes overlay inventory or configuration.

## Failed local repository mutation

Local authoring mutations store untracked lock and journal state under:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/maison/repository-mutations/
```

Each state directory is keyed by the canonical repository path and uses owner-only permissions because journals can copy
private overlay data. If a mutation is interrupted, the next mutation for the same target repository acquires the lock,
recovers incomplete journals, and only then reads repository state. If recovery fails, Maison returns non-zero and
preserves the journal, original copies, candidate copies, and diagnostics. Do not delete the journal directory until the
active repository files and preserved copies are understood.

A busy-lock error means another mutation is still running for that repository, or an interrupted process must finish or
release its lock. Wait for the active command before retrying; if no process remains, rerun the original mutation so the
startup recovery pass can inspect preserved journals.

## Failed user apply

Default `maison user plan` and `maison user apply` do not force replacement of whole-file conflicts. To preview and then
perform the same forced handoff, run:

```bash
maison user plan --force-dotfiles
maison user apply --force-dotfiles
```

The forced plan renders the intended command sequence without modifying files. Use `maison user status` to inspect
current drift before applying. The forced apply backs up the exact targets mise refused before replacement.

Targeted migration backups are stored under:

```text
~/.local/state/maison/backups/git
~/.local/state/maison/backups/dotfiles/<timestamp>
~/.local/state/maison/backups/pi
```

Each dotfile backup contains `manifest.json` and exact file, directory, or symlink payloads. Inspect the manifest before
restoring. It is authoritative for the original home-relative targets and records each entry as `pending` or `restored`.
To restore a snapshot, including replacing paths created by a later convergence, run:

```bash
maison user restore-dotfiles ~/.local/state/maison/backups/dotfiles/<timestamp> --force
```

Restore refuses backup paths outside Maison's dotfile backup root, malformed or escaping manifest entries, and missing
payloads. It stops on the first failed entry; rerun the same command after repair to restore only entries still marked
`pending`. Do not edit the manifest or payload tree unless performing forensic recovery.

Before package convergence on macOS, Maison also sanitizes this backup tree. Any live `.app` bundle is archived
in place as `.app.zip`, unregistered from LaunchServices, and removed only after the archive is non-empty and passes ZIP verification.
Maison also creates `.metadata_never_index` at the backup root. This prevents Mac App Store installers from
relocating future updates into a backup copy instead of `/Applications`. `maison user plan` previews this
migration without modifying the backup.

Restore an archived application bundle only for forensic or recovery purposes:

```bash
ditto -x -k path/to/Application.app.zip /tmp/application-restore
```

Do not leave an extracted `.app` under the Maison backup tree.

A Docker Desktop completion ownership error is repaired only when the conflicting path is a symlink to its exact known
Docker.app completion file. Unrelated paths are not removed. If the retry fails before Docker replaces a removed link,
Maison restores that original link and returns the retry failure. If mise instead rejects Docker Desktop's structured
symlink metadata, Maison delegates only Docker Desktop to Homebrew, ensures the guarded Docker-provided `kubectl` link,
and retries the remaining active-platform packages without Docker. Other cask metadata errors still fail unchanged.

## Failed remote user deployment

Maison records repository transaction state in a root-owned same-filesystem transaction root outside the managed user's writable home. For the default `/home/<user>/.maison` repository path, inspect the root-owned namespace under `/home/.maison-deploy/transactions/<user>/`.
Deployment helpers execute through the `maison-deploy` account with command-scoped sudo elevation for `python3` helper commands and profile activation.

When full `user:apply` fails, the deployment first verifies the staged revision and restores the prior repository through the
root-owned transaction. Only after that revision check succeeds does it run restricted recovery as the managed user from
the restored repository. Recovery repairs dotfiles, mise lock links, non-package mise state, and Maison-owned finalization.
It does not rerun package/app convergence, application-backup migration, legacy Git migration, system activation, or Nix
rollback. An explicit deployment `--force-dotfiles` choice is preserved; force is never enabled during recovery by default.

Recovery writes `remote-convergence-<failed-revision>.json` under
`~/.local/state/maison/recovery/` with the failed/restored revisions, original and recovery exit statuses, completed
recovery steps, and package/app side effects. Package/app changes are not rolled back; when their convergence started or
cannot be determined, the report marks follow-up work as required. The deployment keeps the original user-convergence
failure as its exit status and prints a separate recovery failure when applicable.

If transaction cleanup or rollback itself fails, inspect the journal, staging tree, rollback tree, and lock under the
root-owned transaction root before making changes. Do not delete transaction journals or rollback trees until the active
repository state is understood.

On startup, Maison runs an incomplete-transaction recovery pass before user convergence. If an incomplete repository transaction is detected, it attempts a safe commit or rollback based on durable journal state and revision checks, preserving a recoverable repository path during transitions.

## Failed system deployment

The user phase does not start until the system phase succeeds. On Linux, system activation requires systemd and verifies
hostname, timezone/localtime, SSH configuration/reload, and Maison-managed service units. A mismatch or reload failure
is reported as an activation error with the failing runtime field; it does not proceed to user convergence. With
`auto_rollback` and `magic_rollback` enabled, deploy-rs attempts to restore the prior system profile after activation
failure or loss of confirmation connectivity.

## nix-darwin adoption files

The one-time Darwin preflight may preserve unmanaged files as:

```text
/etc/nix/nix.conf.before-nix-darwin
/etc/nix/nix.custom.conf.before-nix-darwin
```

Retain them until several successful switches have completed.

## Failed repository split or remote transition

If migration validation or remote publication fails, keep the Maison and Terroir staging checkouts, the approved
owner-only manifest, and the original `nix-config` source intact. Do not make `nix-config` public, delete it, or remove
local backups as a recovery step. Re-run privacy, overlay, fresh-history, and remote-state checks before any archive
transition. Secrets and private keys remain in Bitwarden and are never recovered from Git.

## Broken shell

Use `/bin/zsh` or `/bin/bash`, ensure `~/.local/bin` is on `PATH`, and inspect `~/.zshrc` plus `~/.config/maison/zsh`. The shell is user-owned, so repairing it does not require rebuilding the Nix system closure.
