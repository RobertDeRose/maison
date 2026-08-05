# Operations

## Select a consumer

Maison is the framework; the consumer repository is the execution and lock root. Select it explicitly or run from its
Git checkout:

```bash
export MAISON_HOME="$HOME/.maison"
export MAISON_CONSUMER_ROOT="$HOME/src/terroir"
maison doctor
```

The consumer must contain `flake.nix`, `flake.lock`, and `inventory.toml`. Maison's checkout is never used as the
personal deployment root.

## Bootstrap

```bash
./bootstrap.sh --consumer "$HOME/src/terroir" --host "$(hostname -s)"
```

Bootstrap installs verified pinned mise and Lix artifacts, trusts the Maison project configuration, and hands the
selected consumer to the normal bootstrap task. Without a consumer, an interactive run installs only the CLI and prints
next steps; non-interactive runs fail clearly. No neutral Maison inventory is activated as a substitute.

## Preview

```bash
maison system plan
maison user plan
maison plan
```

Planning labels system and user phases and never mutates the consumer or Maison. System planning may realize a Nix
store/cache derivation, but never activates it. User planning renders its dry-run command sequence without invoking mise,
package, dotfile, trust, or migration commands.

```bash
maison user plan --force-dotfiles
maison user apply --force-dotfiles
```

Forced apply snapshots refused dotfile targets under
`~/.local/state/maison/backups/dotfiles/<timestamp>/`. Restore a reviewed snapshot explicitly:

```bash
maison user restore-dotfiles ~/.local/state/maison/backups/dotfiles/<timestamp> --force
```

## Apply

```bash
maison system apply
maison user apply
maison apply
```

`maison apply` activates consumer system state first, then converges consumer user state. A user-layer failure does not
roll back the active Nix generation. Linux activation requires a running systemd runtime and performs the configured
runtime verification.

## Inspect drift and repository state

```bash
maison doctor
maison user status
maison system history
git -C "$MAISON_CONSUMER_ROOT" status --short
```

Maison reports user drift and system generations. Consumer Git history is operator-owned; inspect, pull, commit, and push
it with Git rather than through a Maison repository command.

## Authoring and updates

Authoring commands write only consumer files and require a Git checkout. They reject pre-existing changes in mutation
targets, serialize mutations per repository, and create focused commits after successful transactions:

```bash
maison host add laptop --system aarch64-darwin --user operator
maison tool add github:owner/tool latest
maison package add brew:tool
maison app add ghostty
```

Update the consumer flake independently from Maison:

```bash
maison update                # update the consumer flake.lock
maison update nixpkgs        # update one consumer input
maison update --check        # update, then validate
maison self update            # upgrade Maison from the consumer's pinned input
maison user update           # upgrade consumer mise-managed tools
maison package update        # upgrade consumer Homebrew formulae
maison app update            # upgrade consumer applications
```

`maison update` restores the consumer `flake.lock` if the update or optional validation fails. Maison's lock is never an
implicit fallback. Use `maison self update` when upgrading the framework itself: it updates only the consumer's Maison
input, builds and validates the candidate CLI, and rolls back the lock plus owner-only CLI state on failure. Scheduled
Maison dependency automation updates only Maison's own lock and remains review-gated.

## Deployment

```bash
maison deploy example-linux
```

Deployment requires a clean consumer tree and transfers committed consumer content only. Nix evaluation and deployment
target the consumer flake; Maison's checkout remains untouched. Use a fast-forward-only Git pull or an explicit push for
the consumer before or after deployment when needed.

## Recovery

Repository replacement uses the root-owned transaction boundary and revision-bound rollback. Restricted recovery repairs
only reversible user state, skips package/application side effects, and writes diagnostics under
`~/.local/state/maison/recovery/`. Deployed snapshots are runtime artifacts, not authoring checkouts.

## Validation

```bash
maison check
mise install
mise run check:tests
mise exec -- hk check
```

Run focused subsystem tests while editing, then run the repository suite before committing.
