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

Use an existing consumer directly:

```bash
./bootstrap.sh --consumer "$HOME/src/terroir" --host "$(hostname -s)"
```

For a fresh consumer, use the retained Copier starter:

```bash
./bootstrap.sh --setup "$HOME/src/terroir" --host "$(hostname -s)"
```

Bootstrap renders `overlay_template/` into the separate destination, registers the current host through Maison's
validated `host:add` task, creates the consumer `flake.lock`, and stops for review without activation. Inspect the output,
create the consumer's first Git commit, then rerun with `--consumer` to activate it. The starter is setup-time scaffolding;
the consumer owns all generated files and Git history. Interactive bootstrap without a consumer offers this path;
non-interactive runs require `--consumer` or `--setup`. No neutral Maison inventory is activated as a substitute.

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

## Hidden integration-test prerequisites

Integration tests are deliberate host-side operations and are not part of the public `maison` command surface. Run
hidden tasks directly through the Maison checkout's Mise project:

```bash
mise -C "$MAISON_HOME" tasks --hidden
mise -C "$MAISON_HOME" run test:lume:install
```

`maison tasks`, `maison help`, and generated `maison` completions intentionally omit every `test:*` task. Ordinary
bootstrap, apply, deploy, and update commands never install Lume or mutate host VM tooling.

The macOS lane's host prerequisite is pinned to Trycua CUA release `lume-v0.5.1`, archive
`lume-0.5.1-darwin-arm64.tar.gz`, and SHA-256
`7f10cfbe66a800f98a5db88129f7dc024600fcdc139e0be124845bc7a3dc1359`. The verified launcher is installed at
`${XDG_DATA_HOME:-$HOME/.local/share}/maison/lume/0.5.1/lume` with its adjacent signed `lume.app` bundle on Apple
Silicon macOS 13 or newer. The installer validates the archive before extraction, uses a user-owned concurrency lock,
is idempotent, and fails rather than
replacing an incompatible existing version. It never uses the upstream shell installer, a privileged package manager,
a global PATH change, or a launch agent.

The Lume prerequisite is host-local test infrastructure. It does not install a VM image, alter the production
consumer, or authorize running Darwin bootstrap on the current host outside a disposable VM.

## Linux consumer integration

The Linux integration lane runs only through direct hidden Mise tasks against an explicit external consumer checkout:

```bash
mise -C "$MAISON_HOME" run test:bootstrap:linux -- --consumer "$MAISON_CONSUMER_ROOT"
mise -C "$MAISON_HOME" run test:bootstrap:linux -- --consumer "$MAISON_CONSUMER_ROOT" --dev
mise -C "$MAISON_HOME" run test:deploy -- --consumer "$MAISON_CONSUMER_ROOT"
```

The consumer must be a clean Git checkout. The harness materializes only its committed `HEAD` with `git archive`,
replaces the staged inventory with only a disposable test user and host outside the source checkout, and creates a
new temporary Git history for the stage. It excludes source `.git`, `.beads`, ignored local fnox material,
documentation output, build results, tokens, private keys, and private endpoints. The Maison input must be the public
`RobertDeRose/maison` GitHub node at a full
40-character revision; `bootstrap.sh` is downloaded to a file and its GitHub blob identity is checked against
`git hash-object` before execution.

The lane builds the pinned Maison Apple Container image, creates a disposable systemd container, keeps tokens in
owner-only temporary files, uses public-key-only SSH for deployment, and deletes the container and host staging on
success, failure, or interruption. The unqualified integration command `test:bootstrap` is not retained; the normal
`maison bootstrap` task is unchanged. The upstream `system-manager` read-only `/nix/store` failure is reported as
validation evidence when reproduced and is not hidden or treated as a consumer configuration failure.

## Validation

```bash
maison check
mise install
mise run check:tests
mise exec -- hk check
```

Run focused subsystem tests while editing, then run the repository suite before committing.
