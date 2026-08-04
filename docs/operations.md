# Operations

## Fresh setup with a private overlay

Clone Maison and either provide an existing private overlay or let bootstrap create one with the Copier template:

```bash
git clone https://github.com/OWNER/maison.git
cd maison
MAISON_OVERLAY=GIT-URL-OR-PATH ./bootstrap.sh --host "$(hostname -s)"
```

`--overlay GIT-URL-OR-PATH` takes precedence over `MAISON_OVERLAY`. A local Git path is used directly; a remote URL is
cloned or updated at `${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay`. The legacy
`MAISON_OVERLAY_SOURCE` variable remains accepted after `MAISON_OVERLAY` for compatibility. The selected source and
active path are stored in `${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml`; this owner-only state is never
committed to either repository.

If no overlay is selected, an interactive bootstrap asks whether to set one up now. Yes installs a temporary Copier
runner through Maison's `uv`, renders `overlay_template/`, asks for the private inventory identity, and registers the
current supported macOS/Linux host through `mise run host:add`. No installs and links Maison/the CLI, prints the
follow-up documentation, and exits without installing Nix or activating system/user state. Non-interactive bootstrap
follows the No path unless `MAISON_REQUIRE_OVERLAY=true`, which fails clearly instead.

Bootstrap downloads Maison-owned mise and Lix artifacts to disk, verifies the pinned metadata in
`bootstrap/artifacts.toml`, and executes only verified local files. Do not use pipe-to-shell bootstrap examples.

`maison host add` mutates the active inventory repository and therefore requires that target to be a Git authoring
checkout. With an overlay inventory, new hosts and optional `hosts/<name>/system.nix` stubs are written to the overlay
repository, not to public Maison.

## Preview

```bash
maison system plan
maison user plan
maison plan
```

`maison plan` labels the system and user phases, builds the system preview first, and then renders the user-layer
convergence preview, matching `maison apply`. Interactive terminals show a spinner while system evaluation waits, then
stream the evaluator output; non-interactive runs bypass the spinner and preserve direct output. The system preview may
realize a Nix store/cache derivation, but it never activates the configuration. User planning is read-only: it prints the
exact dry-run command sequence without invoking mise, package, dotfile, trust, or migration commands. Use
`maison user status` to inspect current user-environment drift. Both plan and apply default to non-forced dotfile handling.
Preview a forced replacement before performing it:

```bash
maison user plan --force-dotfiles
maison user apply --force-dotfiles
```

`maison plan --force-dotfiles` forwards the same user-layer flag after the system preview. Planning does not change
files; forced apply snapshots the exact refused targets before replacement. Each snapshot has an atomic `manifest.json`
under `~/.local/state/maison/backups/dotfiles/<timestamp>/`; it records the home-relative
source, file/directory/symlink identity, supported metadata, payload path, symlink target, and restore status. Symlink
payloads remain symlinks, so Maison never copies external symlink target content.

Inspect that manifest before recovery. To restore pending entries from one snapshot, explicitly permit replacement:

```bash
maison user restore-dotfiles ~/.local/state/maison/backups/dotfiles/<timestamp> --force
```

The command accepts only Maison dotfile backup directories, validates manifest paths before mutation, stops at the first
failure, and records each successful restoration so it can be safely retried.

## Apply

```bash
maison system apply
maison user apply
maison apply
```

Linux system activation requires a running systemd runtime. After activation, Maison verifies the configured hostname,
`America/New_York` timezone and `/etc/localtime`, SSH configuration and reload, and the active system-manager and
Maison-managed service units. A mismatch or reload failure returns an actionable error instead of silently continuing.

`maison apply` activates system state first. The user phase starts only after system success. Repository deployment uses revision-bound finalize checks and startup recovery under the root-owned transaction namespace before user convergence starts. If remote user convergence fails, Maison restores and verifies the prior repository, then automatically runs restricted recovery as the managed user. Recovery repairs reversible dotfiles, lock links, non-package mise state, and finalization; it skips package/app convergence and writes a diagnostic under `~/.local/state/maison/recovery/`. Use `--host` for an inventory host. Use `--force-dotfiles` only after reviewing `user:plan`; Maison backs up the exact refused targets before replacement, and recovery preserves that explicit choice.

User package convergence handles one known Docker Desktop cask migration conflict. It removes only six known completion symlinks when each resolves to its exact Docker.app completion source, then retries once. Any regular file, unrelated symlink, or unrelated installer failure remains an error. If the retry fails before Docker replaces a removed link, Maison restores the original link and returns the retry failure.

## Inspect drift

```bash
maison doctor
maison user status
maison system history
```

## Inspect and publish the private overlay

```bash
maison status
maison publish
```

`maison status` inspects only the active private overlay selected by saved state or the environment. It reports the
checkout path, branch, configured upstream, worktree cleanliness, and whether the checkout is in sync, ahead, behind,
diverged, or missing an upstream. It fetches the upstream when possible, with a 30-second bound for the status
fetch. If the fetch fails because the device is offline, credentials/network access are unavailable, or the bound
expires, the command reports the comparison as unavailable and labels any relationship as last-known; it never treats
that result as a current synchronization claim.

`maison publish` uses the overlay's configured upstream and does not select a remote or branch implicitly. It fetches
before changing the worktree and refuses missing, unreachable, behind, or diverged upstreams before stashing. When there
are committed changes to push, it temporarily stashes tracked and untracked files, leaves ignored files untouched,
pushes the existing commits, and restores the stash after success or failure. A push or restoration failure is non-zero;
if restoration conflicts, the stash remains available for explicit recovery. The command never creates a commit for
arbitrary local edits, and an already-current overlay is a successful no-op.

## Validate and develop

```bash
maison check
mise install
mise run check:tests
mise exec -- hk check
```

Repository development tools are owned by the checkout `mise.toml`; normal user convergence does not install them from
the global user config. The Python regression suite is split by subsystem and uses bounded subprocess helpers, so full
`check:tests` runs are deterministic and expected to complete within five minutes on a warm supported development
checkout. Contributors can run focused `python3 -m unittest -v tests.test_<subsystem>` commands while editing one area,
then run `mise -E dev run check` before committing broad validation changes.

Run authoring commands from a Git checkout of the public Maison repository or the private overlay repository being
edited. Deployed snapshots contain `.maison-revision` but not `.git`; they are for runtime apply, plan, status,
deployment finalization, and recovery, not for source edits. If a mutating authoring command is run from a deployed
snapshot, Maison exits non-zero and points back to the authoring checkout or overlay workflow.

## Sync and update

Pull the public Maison checkout and active private overlay, then apply the resulting configuration:

```bash
maison sync
maison sync --user-only
maison sync --force-dotfiles
```

`maison sync` uses fast-forward-only pulls with Git autostash, so local changes are preserved. It stops before apply if
repository synchronization fails. Without an active overlay, it pulls Maison and applies the public configuration.

Update Nix inputs independently when needed:

```bash
maison update                # update flake.lock only
maison update nixpkgs        # update one flake input
maison update --check        # update flake.lock, then run full validation
maison user update           # upgrade mise-managed tools
maison package update        # upgrade Homebrew formulae
maison app update            # upgrade casks and Mac App Store apps
```

Each update surface has an independent failure boundary. `maison update` restores `flake.lock` when the Nix update or optional validation fails. Tool, formula, and application upgrades are explicit and do not activate the system.

Repository-writing commands are authoring-only and serialized per target repository. `tool add`, `tool remove`,
`package add`, `package remove`, `app add`, `app remove`, `host add`, and `update` first require a Git authoring
checkout for the repository they will write, then acquire a fail-fast local mutation lock before reading mutable
repository state. If another mutation is active, Maison exits non-zero and names the busy repository and
journal directory. Read-only plan, status, list, validate, and search commands do not take this lock.

The covered software add/remove commands require an active private Git overlay; they never mutate public Maison as a
fallback. After taking the overlay lock, they refresh it with a fast-forward-only update before reading declaration
files. Tracked and untracked unrelated work is preserved and ignored files are not stashed, while a local change in a
configuration or lockfile that the operation would write is rejected. The refresh does not run full `maison sync`, and a
successful operation creates a focused commit only after its existing install, validation, and transaction journal
complete. If Git commit creation fails, the validated declaration remains in place and the command prints the manual
recovery path.

Scheduled cache refresh automation may update `flake.lock`, build the proposed dependency graph, warm Cachix, and open or refresh an `automation/refresh-flake-lock` pull request. It does not merge that PR or bypass branch protection; accepting dependency changes remains a normal reviewed PR merge.

The archived source repository and the approved migration manifest remain recovery references until the new Maison
overlay workflow has been confirmed on the managed hosts. Do not remove local migration
backups before that confirmation; the remote archive does not delete local recovery data.

## Clean

```bash
maison system clean 7d
```

This removes old system generations from the canonical platform profile, then runs Nix store garbage collection. User tool caches are maintained separately.

## Add software

```bash
maison package search helix
maison tool add github:owner/tool latest
maison package add brew:tool
maison app add ghostty
```

Add operations commit configuration only after successful installation or resolution. Package mutation does not silently assign ownership to Nix.
