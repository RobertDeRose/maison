# Maison

Maison is the command interface for a two-layer macOS and Linux configuration repository:

- **Nix/Lix owns operating-system state.** nix-darwin configures Apple Silicon macOS; system-manager configures supported non-NixOS Linux hosts.
- **mise owns user state.** It installs user tools, ordinary Homebrew formulae and casks, Mac App Store applications, current-user preferences, and dotfiles.

Home Manager is intentionally absent. `nh` provides the local nix-darwin workflow, while `deploy-rs` handles remote system-manager profiles and connection-aware system rollback.

`RobertDeRose/maison` is the public framework repository. Personal and site-specific configuration lives in the
private `RobertDeRose/terroir` overlay; Bitwarden remains the source of truth for secrets and private keys. The former
`RobertDeRose/nix-config` repository is retained as the private archived migration source.

## Ownership boundary

| Nix/Lix                                        | mise                                    |
|------------------------------------------------|-----------------------------------------|
| Nix daemon, caches, GC, and store policy       | Developer tools and language runtimes   |
| PAM, Apple Watch/Touch ID sudo, sudoers        | Ordinary Homebrew formulae and casks    |
| Hostname, timezone, locale, users              | Mac App Store applications              |
| Root-owned files and SSH daemon policy         | Git, SSH client, Zsh, Starship, editors |
| System launchd/systemd services                | User LaunchAgents/systemd units         |
| Machine-wide or privileged macOS policy        | Current-user macOS preferences          |
| System-wide fonts and OS-integrated installers | User dotfiles and Tera templates        |

A file, package, service, or preference must have exactly one owner.

## Supported systems

- `aarch64-darwin`
- `aarch64-linux`
- `x86_64-linux`

Intel macOS is deliberately unsupported rather than partially configured.

## Common commands

```bash
maison doctor
maison plan
maison apply
maison update

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

The same operations are available as mise tasks, for example `mise run system:plan`.

`maison apply` is deliberately system-first:

1. Build and activate the Nix system configuration.
2. Converge the mise user environment only after system activation succeeds.

A user-layer failure does not roll back the active Nix generation. A system-layer failure prevents the user phase from starting.

## Flake outputs

```text
darwinConfigurations.<host>   nix-darwin system closure
systemConfigs.<host>           system-manager system closure
deploy.nodes.<host>            deploy-rs Linux deployment
packages.<system>.nh           local system UX
packages.<system>.deploy-rs    remote system deployment
checks.<system>.*              inventory, host, schema, and activation checks
```

There are no `homeConfigurations` outputs.

## Configuration layout

```text
flake.nix                     system inputs
inventory.toml                neutral starter users, hosts, profiles, deploy endpoints
nix/                          OS-level modules and deployment definitions
config/mise/                  starter user tools, packages, preferences, locks
dotfiles/                     starter native user configuration files
.mise/tasks/system/           Nix/nh/deploy-rs workflows
.mise/tasks/user/             mise bootstrap workflows
scripts/                      migration, package, and deployment transactions
mise.toml                     repository tools, task discovery, and dotfile declarations
mise.lock                     locked repository development tool artifacts
```

Platform-specific mise files are selected through `.miserc.toml` and `auto_env = true`:

- `config.toml`: cross-platform tools and ordinary Homebrew formulae.
- `config.macos.toml`: macOS-only tools, including AI coding tools, plus current-user preferences.
- `config.macos-arm64.toml`: Apple Silicon casks, Mac App Store applications, and macOS-only formulae.
- `config.linux.toml`: Linux-specific package-manager and locale policy.

Repository validation tools are owned by the checkout `mise.toml`, not the global user config. Normal machine convergence does not install them unless it is run from this repository. The flake formatter reads the `nixfmt-rs` artifact from `mise.lock`, so hooks and `nix fmt` cannot drift to different formatter versions.

## Repository boundary

```text
public  RobertDeRose/maison   reusable framework, neutral examples, tests, and tooling
private RobertDeRose/terroir  inventory, hosts, personal/site configuration, and non-secret trusted data
archive RobertDeRose/nix-config complete historical migration source and rollback reference
```

Maison owns the framework and command surface. Terroir is an ordinary Git checkout that mirrors Maison-owned overlay
paths such as `inventory.toml`, `hosts/`, `config/mise/`, `dotfiles/`, and non-secret trusted configuration. Neither
repository stores passwords, tokens, secret values, SSH private keys, or signing private keys.

## Private overlay

The public repository is the reusable Maison vehicle. Real hosts, usernames, emails, deploy targets, site packages, dotfile overrides, and trusted key material belong in a tracked private overlay repository.

Overlay discovery uses this precedence:

1. `--overlay <git-url-or-path>` for the current bootstrap run.
2. `MAISON_OVERLAY_SOURCE`, including a value supplied by mise secrets.
3. `${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml`.

The overlay is cloned or updated at `${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay`. If the overlay contains `inventory.toml`, Maison uses that typed inventory for Python validation, task lookups, host overrides, Nix outputs, and deployment targeting. Without an overlay, the neutral public starter inventory remains valid for examples and checks.

## Bootstrap

From an existing checkout:

```bash
./bootstrap.sh --host "$(hostname -s)" --overlay GIT-URL-OR-PATH
```

Or from a downloaded bootstrap artifact:

```bash
curl -fsSLO https://raw.githubusercontent.com/RobertDeRose/maison/main/bootstrap.sh
# Verify bootstrap.sh against the reviewed release checksum before running it.
bash bootstrap.sh --host "$(hostname -s)" --overlay git@github.com:RobertDeRose/terroir.git
```

Bootstrap installs verified pinned mise and Nix/Lix artifacts when missing, stores or refreshes the overlay source, applies the Nix system layer, then applies user state. Bootstrap verification metadata lives in `bootstrap/artifacts.toml`. The canonical framework clone target is `RobertDeRose/maison`; a real host should provide `RobertDeRose/terroir` as its overlay. Non-interactive setup fails with an actionable message when an overlay is required but no source is available.

Before the first real switch on an existing machine:

```bash
maison check
maison system plan
maison user plan
```

## Deployment safety

`maison deploy <host>` requires a clean working tree. It creates a revision-stamped archive from `git archive`, so `.git`, ignored files, untracked files, local credentials, and dirty edits are never transferred.

The remote repository replacement uses a privileged transaction boundary:

1. Validate that `repo_path` is a normalized descendant of `/home/<managed-user>`.
2. Allocate a root-owned transaction root on the same filesystem outside the managed user's writable home.
3. Stage the archive, rollback copy, lock, and journal under that root-owned transaction root.
4. Run `user:apply` as the managed user from the staged repository.
5. Finalize or roll back through the journaled privileged transaction state.

Maison fails closed when no safe same-filesystem root-owned transaction root is available.

Deploy-rs still owns the separate system-profile rollback boundary.

## Package convergence

Configuration mutators stage and validate candidate files before replacing repository state. `tool:add`, `package:add`, `app:add`, and `host:add` leave the checked-in configuration unchanged when resolution, installation, or validation fails.

Docker Desktop can leave completion symlinks that predate mise's cask ownership record. During `user:apply`, Maison handles only that exact conflict: a symlink is removed only when it resolves to Docker.app's known completion source, after which package convergence is retried once. Unrelated files and unrelated cask failures remain errors.

## Reproducibility boundary

Nix inputs are pinned by `flake.lock`. Mise lockfiles preserve resolved user and contributor tool versions where metadata exists, but user configuration intentionally retains `latest` declarations and permits network resolution for missing entries. This is repeatable workstation convergence, not strict offline or byte-for-byte reproduction.

Review the [architecture](docs/architecture.md), [deployment guide](docs/deployment.md), [migration contract](docs/migration-contract.md), and [recovery guide](docs/recovery.md) before deleting old generations or backups.

## Development workflow

Maison uses the dstack documentation-first, Beads-backed workflow for planned work.
Use `/plan-features`, `/start-feature <slug>`, `/implement-feature <slug>`,
and `/close-feature <slug>` to keep designs, tasks, validation, and delivery
records aligned.
