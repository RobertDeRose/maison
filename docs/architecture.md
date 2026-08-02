# Architecture

## Principle

Maison separates configuration by privilege boundary:

```text
Nix/Lix system layer
├── nix-darwin on Apple Silicon macOS
├── system-manager on Linux
├── nh for local Darwin builds and switches
└── deploy-rs for remote Linux system profiles

mise user layer
├── tools and runtimes
├── ordinary Homebrew formulae, casks, and MAS apps
├── dotfiles and Tera templates
├── current-user macOS defaults
└── user services
```

The supported systems are `aarch64-darwin`, `aarch64-linux`, and `x86_64-linux`. Intel macOS is rejected by bootstrap, inventory validation, mise lock platforms, Nix outputs, and CI.

## Public Maison and private overlays

Maison is the public framework repository. It owns reusable code, validators, task machinery, Nix modules, and neutral
starter examples. Each user or organization may create a private plain-Git overlay for real site state: inventory, host
overrides, package declarations, dotfiles, preferences, and non-secret trusted configuration.

Secrets, passwords, tokens, SSH private keys, and signing private keys belong in Bitwarden, not in Maison or an overlay.

Overlay state is local and untracked:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml
${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay
```

`--overlay` has run-local precedence over `MAISON_OVERLAY_SOURCE`, and both precede the saved state record. A private
overlay mirrors Maison's layout for owned data: `inventory.toml`, `hosts/`, `config/mise/*.toml`, `dotfiles/`, and
trusted key files. Overlay state is local and untracked; no checkout or state file is committed to Maison.

## Nix system layer

The flake exports `darwinConfigurations`, `systemConfigs`, and `deploy`.

### macOS

nix-darwin owns Nix/Lix daemon policy, primary-user registration, system shells, Apple Watch and Touch ID sudo, PAM, login-window policy, Caps Lock remapping, host identity, time zone, services, system-wide fonts, and OS-integrated installers such as FUSE-T.

Ordinary applications and interactive CLI packages do not belong in `environment.systemPackages`.

### Linux

system-manager owns hostname, locale, time zone, managed users, sudoers, SSH daemon includes, root-owned Nix configuration, authorized-key refresh, and system services. MAISON-015 supports systemd-backed Linux hosts only: activation verifies the active hostname, timezone and `/etc/localtime`, SSH configuration/reload, and Maison-managed service units. A dedicated `maison-deploy` account owns privileged deployment and repository-transaction entrypoints, and its sudoers policy is command-scoped rather than `NOPASSWD: ALL`. The system closure also retains the minimal curl, Git, and tar prerequisites required before the mise user layer exists.

`/nix/var/nix/profiles/system-manager-profiles/system-manager` is the canonical Linux system profile.

Upstream system-manager Rust tests remain enabled. Maison no longer overrides `rustPlatform.buildRustPackage` to disable checks.

## nh

Darwin planning and activation use:

```bash
nh darwin build  . -H <host>
nh darwin switch . -H <host>
```

Tasks fall back to `nix run .#nh` before the system profile has installed `nh`. Linux local activation remains a small adapter around the pinned system-manager CLI because `nh` does not currently expose a system-manager command.

## deploy-rs

Each deploy-enabled Linux inventory host becomes `deploy.nodes.<host>`. Its system profile:

- Uses the canonical system-manager profile path.
- Runs through the deployment account with command-scoped privilege elevation.
- Activates the exact closure selected by deploy-rs through `$PROFILE/bin/activate` for normal and boot activation.
- Supports a side-effect-free dry activation check.
- Enables `autoRollback` and `magicRollback` from inventory.

The local deploy-rs adapter uses the same `pkgs.deploy-rs` package for the CLI, remote activation binary, and matching JSON schema. CI builds the schema and activation checks instead of merely evaluating their derivation paths.

## mise user layer

The repository `mise.toml` owns repository development tools and task discovery. The installed global configuration owns
the Maison runtime tool (`usage`) and any user tools supplied by a private overlay. Repository development tools are
installed explicitly for this checkout by `maison check`, documentation tasks, and CI.

Node is intentionally scoped at both levels: the global configuration keeps a user runtime for standalone Pi use, while
repository `mise.toml` pins Node 24 for reproducible TypeScript validation. The repository declaration wins inside the
checkout and does not converge or replace the global user runtime.

A private overlay may own:

- Cross-platform tools and ordinary Homebrew formulae in `config/mise/config.toml`.
- macOS-only tools and preferences in `config/mise/config.macos.toml`.
- Apple Silicon casks and MAS applications in `config/mise/config.macos-arm64.toml`.
- Linux-specific policy in `config/mise/config.linux.toml`.
- Application configuration in native formats under `dotfiles/`; Tera is used only where host, user, or platform
  interpolation is required.

Public Maison keeps these policy files empty and schema-valid.

## macOS defaults boundary

Mise may write current-user preference domains such as Dock, Finder, trackpad, screenshots, and application preferences. It must not own `sudo defaults` domains, `/Library/Preferences`, login-window policy, authentication policy, PAM, or host-scoped `defaults -currentHost` values.

## Single ownership

Package declarations merge across mise's configuration hierarchy. A private overlay should declare common packages once
in `config/mise/config.toml` and platform additions in the matching files. Public Maison declares no user packages or
applications. A binary must not be declared simultaneously as a mise tool and a bootstrap package.

## Inventory interface

Shell tasks do not parse TOML with awk. `schemas/inventory.toml` is the public schema contract for supported systems,
profiles, feature keys, deploy keys, and defaults. `.mise/lib/inventory.py` uses Python's `tomllib` for validation and
typed lookups, and Nix imports the same schema contract before constructing outputs. Shared valid and invalid fixtures
under `tests/fixtures/inventory/` keep both validators aligned in CI. When an overlay inventory is present, Python tasks
use that file and validate its sibling `hosts/` overrides; Nix receives the active overlay as its explicit `overlay`
flake input and evaluates the corresponding inventory and host override tree without impure evaluation. In particular,
remote repository paths must be normalized descendants of
`/home/<managed-user>` and cannot be `/`, a home directory, or a path containing traversal segments.

## Transaction boundaries

Local repository mutation commands require a Git authoring checkout for the target repository they write. A deployed
snapshot has `.maison-revision` but no `.git` and is runtime source only; authoring commands fail there with guidance to
edit the public source checkout or private overlay repository instead. `host:add` checks the active inventory repository,
so a deployed public Maison snapshot may still author hosts in a private overlay clone when that overlay is a Git
checkout.

Local repository mutation commands serialize checked-in or overlay repository writes through one target-repository lock.
`tool:add`, `tool:remove`, `package:add`, `package:remove`, `app:add`, `app:remove`, `host:add`, and `update` acquire a
fail-fast local `fcntl` lock before reading mutable repository state. Their untracked journals live under
`${XDG_STATE_HOME:-$HOME/.local/state}/maison/repository-mutations/`, or under `MAISON_REPOSITORY_MUTATION_STATE_DIR`
for tests, keyed by the canonical target repository path with owner-only permissions. The journal copies original and
candidate files so startup recovery can restore incomplete local mutations before a new mutation reads state.

```text
maison apply
  1. system:apply  (Nix generation semantics)
  2. user:apply    (mise convergence semantics)
```

A failed system activation stops before user convergence. A failed user convergence leaves the active system generation in place.

Remote deployment has an additional repository transaction around the user phase. If remote user convergence fails,
Maison verifies the restored repository revision before running restricted recovery as the managed user. Recovery repairs
only reversible user state; package and application side effects remain outside rollback and are reported for follow-up. Transaction journals, locks, staging trees, and rollback trees are privileged state and live in a root-owned same-filesystem transaction root outside the managed user's writable home. The managed user may read and apply the staged repository, but must not be able to unlink, replace, or edit transaction control state. Deploy-rs independently protects the Linux system profile while only the `maison-deploy` account can launch privileged activation actions.

The local repository mutation journal is separate from that privileged remote deployment namespace. Local authoring locks
must not weaken the root-owned transaction root, same-filesystem constraints, or revision-bound remote rollback
contracts.
