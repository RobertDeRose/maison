# Architecture

## Principle

Maison separates configuration by privilege and repository boundary:

```text
Maison framework repository
├── reusable Nix modules, validators, task machinery, and CLI
├── neutral inventory/schema fixtures and documentation
└── framework development and release lock

Consumer repository
├── flake.nix and flake.lock
├── inventory.toml and hosts/
├── config/mise/ and dotfiles/
└── deployment and personal configuration state

Nix/Lix system layer
├── nix-darwin on Apple Silicon macOS
├── system-manager on Linux
├── nh for local Darwin builds and switches
└── deploy-rs for remote Linux system profiles

mise user layer
├── consumer tools and runtimes
├── ordinary Homebrew formulae, casks, and MAS apps
├── consumer dotfiles and Tera templates
├── current-user macOS defaults
└── user services
```

The consumer is the execution and lock root. Maison's checkout is never a personal deployment root and consumer commands
do not update or write its files.

Supported systems are `aarch64-darwin`, `aarch64-linux`, and `x86_64-linux`. Intel macOS is rejected by bootstrap,
inventory validation, mise lock platforms, Nix outputs, and CI.

## Framework and consumer repositories

Maison is provider-neutral. It owns reusable code, validators, task machinery, Nix modules, public schemas, neutral
fixtures, and the CLI runtime. It does not own personal users, real hosts, deployment endpoints, package selections,
dotfiles, or consumer locks.

A consumer repository owns the files for one installation:

- `flake.nix` composes Maison's public inputs and exports consumer host outputs;
- `flake.lock` pins that consumer's inputs;
- `inventory.toml` describes users, hosts, profiles, and deployment targets;
- `hosts/` contains host-specific system overrides;
- `config/mise/` and `dotfiles/` contain user policy; and
- Git history is the source of deployment and authoring state.

Commands select the consumer in this order:

1. `MAISON_CONSUMER_ROOT`;
2. compatibility aliases `MAISON_REPOSITORY` or `MAISON_REPO`; and
3. the Git checkout containing the current working directory when it is not Maison.

Packaged or explicit CLI invocations reject Maison itself as the consumer. Direct `mise` use from a Maison checkout is
reserved for framework development and validation; authoring helpers still refuse to mutate that checkout.

Consumers declare logical confidential values in `fnox.toml` and choose their provider. Secrets, passwords, tokens,
SSH private keys, and signing private keys resolve only at runtime and belong in the selected provider, not in either
repository or the Nix store.

### Fresh consumer setup

Maison retains `overlay_template/` as a Copier starter for new consumer repositories. `bootstrap.sh --setup PATH`
renders it into a destination separate from Maison, registers the current host through the consumer `host:add` task,
pins the generated consumer flake, and stops for review before activation. After the operator creates the consumer's first
commit, normal bootstrap uses that consumer. This template is a setup-time scaffold, not a second runtime configuration
root: Maison does not save, hide, synchronize, publish, or otherwise manage an alternate consumer path.

The canonical consumer is Terroir. The archived private `terroir.original` checkout is migration input only, and the
former `nix-config` source is a private archived framework reference; neither is an active Maison input. Maison's public
history is fresh and contains only reusable, neutral content. The migration manifest determines what belongs in Terroir.

## Nix system layer

The framework exposes reusable modules and public helpers. A consumer composes them into its own
`darwinConfigurations`, `systemConfigs`, and `deploy` outputs.

### macOS

nix-darwin owns Nix/Lix daemon policy, primary-user registration, system shells, Apple Watch and Touch ID sudo, PAM,
login-window policy, Caps Lock remapping, host identity, time zone, services, system-wide fonts, and OS-integrated
installers such as FUSE-T. Ordinary applications and interactive CLI packages do not belong in
`environment.systemPackages`.

### Linux

system-manager owns hostname, locale, time zone, managed users, sudoers, SSH daemon includes, root-owned Nix
configuration, authorized-key refresh, and system services. Linux activation verifies systemd, hostname, timezone and
`/etc/localtime`, SSH configuration/reload, and Maison-managed service units. A dedicated `maison-deploy` account owns
privileged deployment and repository-transaction entrypoints with command-scoped sudo rather than `NOPASSWD: ALL`.

`/nix/var/nix/profiles/system-manager-profiles/system-manager` is the canonical Linux system profile.

Upstream system-manager Rust tests remain enabled. Maison does not override package checks to disable them.

## nh and deploy-rs

Darwin planning and activation use the consumer flake:

```bash
nh darwin build  /path/to/consumer -H <host>
nh darwin switch /path/to/consumer -H <host>
```

Tasks fall back to Maison's public `nh` app before the system profile installs `nh`. Linux local activation uses the
pinned system-manager CLI because `nh` does not expose a system-manager command.

Each deploy-enabled Linux consumer host becomes `deploy.nodes.<host>`. Its profile uses the canonical system-manager
closure, command-scoped deployment privilege, exact `$PROFILE/bin/activate` activation, and inventory-controlled
`autoRollback` and `magicRollback`. The local deploy-rs adapter uses one `pkgs.deploy-rs` package for its CLI, remote
activation binary, and matching schema.

## mise user layer

Maison's `mise.toml` owns framework development tools and task discovery. The selected consumer's
`config/mise/config.toml` is the global user layer. Maison's project configuration remains the project layer, so running
consumer commands does not dirty the Maison checkout.

During user convergence, Maison temporarily hides installed symlinks that point into the consumer configuration so mise
can resolve relative dotfile sources from the consumer. Successful convergence retains the new consumer targets; dry-runs
and failures restore the installed links.

Consumer package policy may own:

- cross-platform tools and Homebrew formulae in `config/mise/config.toml`;
- macOS tools and preferences in `config/mise/config.macos.toml`;
- Apple Silicon casks and MAS applications in `config/mise/config.macos-arm64.toml`;
- Linux-specific policy in `config/mise/config.linux.toml`; and
- native application configuration under `dotfiles/`.

## macOS defaults boundary

Mise may write current-user preference domains such as Dock, Finder, trackpad, screenshots, and application preferences.
It must not own `sudo defaults` domains, `/Library/Preferences`, login-window policy, authentication policy, PAM, or
host-scoped `defaults -currentHost` values.

## Inventory interface

Shell tasks do not parse TOML with awk. `schemas/inventory.toml` is the public schema contract for supported systems,
profiles, feature keys, deploy keys, and defaults. `.mise/lib/inventory.py` uses Python `tomllib` for typed lookups, and
Nix imports the same schema contract before constructing outputs. Shared fixtures keep both validators aligned.

The consumer inventory replaces Maison's neutral starter inventory; it is not merged with it. Host override directories
are resolved relative to the consumer root and are allowed only when they match an inventory host.

## Transaction boundaries

Local authoring commands require a Git checkout of the selected consumer. A deployed snapshot has `.maison-revision` but
no `.git` and is runtime source only. `host:add`, tool/package/app mutations, and `update` fail rather than writing
Maison or a deployed snapshot.

Local mutations serialize checked-in consumer writes through one target-repository lock. Journals live under
`${XDG_STATE_HOME:-$HOME/.local/state}/maison/repository-mutations/` or the test override
`MAISON_REPOSITORY_MUTATION_STATE_DIR`, keyed by the canonical consumer path with owner-only permissions. A journal
copies original and candidate files so startup recovery can restore an incomplete mutation before reading mutable state.

Covered add/remove operations preserve unrelated tracked and untracked work, ignore ignored files, and reject dirty
declaration or lock targets. Once validation and the journal complete, only the operation's declaration and generated lock
paths enter a focused commit. Maison does not fetch, pull, or push the consumer:

```text
added(scope): `identifier`
removed(scope): `identifier`
```

A commit failure is post-transaction: validated consumer files remain in place for manual recovery and external package or
application effects are not rolled back.

Remote deployment has an additional repository transaction around the consumer user phase:

```text
maison apply
  1. system:apply  (consumer Nix generation)
  2. user:apply    (consumer mise convergence)
```

A failed system activation stops before user convergence. A failed user convergence leaves the active system generation in
place. Deployment archives only committed consumer content, stages it through a root-owned same-filesystem transaction,
and restores the prior consumer revision before restricted recovery. Package/application side effects remain follow-up
work and are recorded in the recovery report.

The local mutation journal and the privileged remote deployment namespace are separate safety boundaries.
