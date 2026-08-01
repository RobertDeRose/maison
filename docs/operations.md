# Operations

## Fresh setup with a private overlay

Clone the public framework and supply the private Terroir overlay for a real host:

```bash
git clone https://github.com/RobertDeRose/maison.git
cd maison
./bootstrap.sh --host "$(hostname -s)" --overlay git@github.com:RobertDeRose/terroir.git
```

Use `--overlay` during bootstrap, or set `MAISON_OVERLAY_SOURCE` from the environment or a mise secret:

```bash
./bootstrap.sh --host "$(hostname -s)" --overlay GIT-URL-OR-PATH
```

Bootstrap downloads Maison-owned mise and Lix artifacts to disk, verifies the pinned metadata in `bootstrap/artifacts.toml`, and executes only verified local files. Do not use pipe-to-shell bootstrap examples.

Maison stores the selected Terroir source in `${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml` and clones or updates it at `${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay`. Interactive bootstrap may prompt for the overlay source when it is required; non-interactive bootstrap fails instead of continuing with public starter data for a real machine. The overlay state is machine-local and never committed to either repository.

`maison host add` mutates the active inventory repository and therefore requires that target to be a Git authoring
checkout. With an overlay inventory, new hosts and optional `hosts/<name>/system.nix` stubs are written to the overlay
clone, not to public Maison.

## Preview

```bash
maison system plan
maison user plan
maison plan
```

`maison plan` previews the system layer first and then the user layer, matching `maison apply`. For the same user flags,
user plan and apply use the same convergence steps; dry-run execution and the documented package/trust/finalize
substitutions are the only differences. Both default to non-forced dotfile handling. Preview a forced replacement before
performing it:

```bash
maison user plan --force-dotfiles
maison user apply --force-dotfiles
```

`maison plan --force-dotfiles` forwards the same user-layer flag after the system preview. Forced plan reports ownership
conflicts without changing files; forced apply snapshots the exact refused targets before replacement. Each snapshot has
an atomic `manifest.json` under `~/.local/state/maison/backups/dotfiles/<timestamp>/`; it records the home-relative
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

## Update

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

Scheduled cache refresh automation may update `flake.lock`, build the proposed dependency graph, warm Cachix, and open or refresh an `automation/refresh-flake-lock` pull request. It does not merge that PR or bypass branch protection; accepting dependency changes remains a normal reviewed PR merge.

The archived `RobertDeRose/nix-config` repository and the approved migration manifest remain recovery references until the
new Maison/Terroir workflow has been confirmed on the managed hosts. Do not archive or remove local migration backups
before that confirmation.

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
