# Maison

Maison is a reusable macOS and Linux configuration framework:

- **Nix/Lix owns operating-system state.** nix-darwin configures Apple Silicon macOS; system-manager configures supported non-NixOS Linux.
- **mise owns user state.** The consumer repository supplies tools, packages, applications, preferences, and dotfiles.

Home Manager is intentionally absent. `nh` provides the local nix-darwin workflow, while `deploy-rs` handles remote
system-manager profiles and connection-aware system rollback.

Maison is provider-neutral. It contains framework code, neutral examples, tests, and bootstrap tooling—not a
maintainer's personal application list, deployment target, or dotfiles.

## Public flake

Consumers pin Maison as a flake input and keep their own flake, lock file, inventory, host topology, configuration, and
deployment state:

```bash
nix run github:RobertDeRose/maison#maison -- --help
nix flake check --no-update-lock-file
```

The public flake exports the CLI package and app, reusable nix-darwin and system-manager modules, the orchestration
library, the inventory schema, and neutral validation fixtures. See the [public flake reference](docs/src/reference/flake.md)
and [consumer reference](docs/src/reference/consumer.md).

## Quickstart

Create or clone a consumer repository first. For example, Terroir can own the personal inventory and configuration while
Maison remains the reusable framework:

```bash
git clone git@github.com:RobertDeRose/terroir.git "$HOME/src/terroir"
```

Install Maison from a reviewed release and select the consumer explicitly:

```bash
MAISON_BOOTSTRAP_VERSION="v0.1.1"
bash bootstrap.sh --consumer "$HOME/src/terroir" --ref "$MAISON_BOOTSTRAP_VERSION"
```

The bootstrap script installs Maison under `~/.maison` when needed, links the `maison` command, verifies pinned
platform artifacts, and hands control to the consumer repository. It never uses the Maison checkout as the personal
execution or deployment root.

For a local Maison checkout:

```bash
MAISON_HOME="$PWD" MAISON_CONSUMER_ROOT="$HOME/src/terroir" ./bin/maison plan
```

## Consumer repository

A consumer repository must contain regular, committed files named `flake.nix`, `flake.lock`, and `inventory.toml`.
It normally also owns `hosts/`, `config/mise/`, `dotfiles/`, and any host-specific Nix modules. Maison commands resolve
the consumer in this order:

1. `MAISON_CONSUMER_ROOT`;
2. `MAISON_REPOSITORY` or `MAISON_REPO` as compatibility aliases;
3. the Git checkout containing the current working directory, when it is not the Maison installation.

Maison's own checkout is rejected as a consumer for packaged or explicit CLI invocations. Set the canonical environment
variable in scripts and CI:

```bash
export MAISON_HOME="$HOME/.maison"
export MAISON_CONSUMER_ROOT="$HOME/src/terroir"
maison plan
```

The consumer's flake should import Maison's public modules and compose its own host outputs. Maison's `flake.lock` is
only for Maison development, validation, and release; consumer commands never update it.

Declare logical confidential values in the consumer's `fnox.toml` and let the consumer choose the fnox provider.
Passwords, tokens, SSH private keys, signing private keys, and other secret material resolve at runtime; they never
belong in Maison, the consumer Git history, Nix expressions, process arguments, or the Nix store. A private Git
repository is not a substitute for secret storage. See the [fnox reference](docs/src/reference/fnox.md).

## Bootstrap behavior

`bootstrap.sh` accepts `--consumer PATH` or `MAISON_CONSUMER_ROOT`. The selected repository must already contain the
consumer flake, lock, and inventory. Running without a consumer installs or repairs only the Maison CLI and prints the
next step; non-interactive runs fail clearly instead of activating neutral or Maison-owned state.

Bootstrap first installs verified pinned mise, trusts only the Maison project configuration, installs verified Nix/Lix
artifacts when needed, and runs the bootstrap task with the consumer root. Use `--user-only` on the mise task when system
activation should be skipped. Do not use pipe-to-shell bootstrap examples; verify downloaded bootstrap artifacts against
`bootstrap/artifacts.toml` before execution.

## Common commands

Run commands from the consumer checkout or set `MAISON_CONSUMER_ROOT`:

```bash
maison doctor
maison consumer validate
maison plan
maison apply
maison update
maison self update

maison system plan
maison system apply
maison system history
maison system rollback
maison system clean

maison user plan
maison user apply
maison user status
maison user update

maison deploy example-linux
```

`maison consumer validate` runs the read-only consumer contract: flake composition, inventory, mise package and dotfile
declarations, fnox references, documentation links, supported systems, and raw-credential/private-key boundaries. It
never activates a system, mutates a lock file, or invokes fnox providers, so CI does not need personal credentials.

`maison self update` upgrades only the Maison input in the selected consumer's `flake.lock`. It builds the locked
candidate CLI, validates the consumer through that candidate, and records the candidate CLI in owner-only local state;
failed updates restore both the lock and the prior CLI state. Maison's own checkout and lock are never an update target.

The same operations are available as Maison mise tasks, for example `mise -C ~/.maison run system:plan`. Authoring
commands write only consumer files. They require a Git checkout, reject pre-existing changes in mutation targets, and
create focused commits only after successful transactions. Use Git for consumer history, with fast-forward-only pulls
when you choose to synchronize it.

`maison apply` is deliberately system-first: it activates the consumer's Nix system layer and then converges its user
layer. A user-layer failure does not roll back the active Nix generation.

## Deployment and recovery

`maison deploy <host>` requires a clean consumer working tree and transfers committed consumer content only. Nix
planning and deployment target the consumer flake; the Maison checkout and lock remain untouched.

Repository replacement uses a root-owned transaction boundary and revision-bound rollback. Restricted recovery repairs
only reversible user state; package and application side effects are not rolled back. See the [architecture](docs/architecture.md),
[deployment guide](docs/deployment.md), [recovery guide](docs/recovery.md), and [package policy](docs/package-policy.md).

## Ownership boundary

| Nix/Lix                                  | mise                          |
|------------------------------------------|-------------------------------|
| Nix daemon, caches, GC, and store policy | User tools and runtimes       |
| PAM, sudoers, and privileged policy      | Homebrew formulae and casks   |
| Hostname, timezone, locale, users        | Mac App Store applications    |
| Root-owned files and SSH daemon policy   | User dotfiles and preferences |
| System launchd/systemd services          | User services                 |
| System-wide fonts and OS integrations    | Non-privileged configuration  |

A file, package, service, or preference must have exactly one owner. Consumer-owned state is never silently copied into
or written to Maison.

## Repository layout

```text
flake.nix                         Maison development/release inputs
inventory.toml                    neutral Maison validation inventory
nix/                              reusable OS modules and orchestration helpers
.mise/tasks/                      Maison framework workflows
scripts/                          bootstrap, validation, and deployment transactions
mise.toml                         Maison development tools and task discovery
mise.lock                         Maison development tool lock
schemas/                          public inventory schema
```

Consumer repositories own their `flake.nix`, `flake.lock`, inventory, host overrides, mise policy, dotfiles, deployment
state, and personal configuration.

## Development

Maison uses repository-owned mise tools and dstack/Beads workflow controls:

```bash
mise install --locked
mise run check
uv run scripts/check-docs.py
mise exec -- hk check
```

Use `/plan-features`, `/start-feature <slug>`, `/implement-feature <slug>`, and `/close-feature <slug>` for planned work.
