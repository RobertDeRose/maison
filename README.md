# Maison

Maison is a reusable two-layer macOS and Linux configuration framework:

- **Nix/Lix owns operating-system state.** nix-darwin configures Apple Silicon macOS; system-manager configures supported non-NixOS Linux.
- **mise owns optional user state.** A private overlay can provide tools, packages, applications, preferences, and dotfiles.

Home Manager is intentionally absent. `nh` provides the local nix-darwin workflow, while `deploy-rs` handles remote
system-manager profiles and connection-aware system rollback.

Maison is intentionally generic. It contains framework code, neutral examples, tests, and bootstrap tooling—not a
maintainer's personal application list or dotfiles.

## Quick start

Clone Maison and create or select a private overlay:

```bash
git clone https://github.com/RobertDeRose/maison.git
cd maison
cp -R examples/terroir/. "$HOME/src/my-maison-overlay/"
cd "$HOME/src/my-maison-overlay"
$EDITOR inventory.toml config/mise/config.toml
git init
git add .
git commit -m 'chore: initialize private Maison overlay'
```

Create a private remote for that overlay, then bootstrap from the Maison checkout:

```bash
cd /path/to/maison
./bootstrap.sh \
  --host "$(hostname -s)" \
  --overlay git@github.com:OWNER/my-maison-overlay.git
```

The overlay repository can use any name, hosting service, or access model. `examples/terroir/` is only a neutral
starting layout; `terroir` is not a required repository name.

Before the first real switch on an existing machine:

```bash
maison check
maison system plan
maison user plan
```

## Ownership boundary

| Nix/Lix                                  | mise                                   |
|------------------------------------------|----------------------------------------|
| Nix daemon, caches, GC, and store policy | Optional user tools and runtimes       |
| PAM, sudoers, and privileged policy      | Optional Homebrew formulae and casks   |
| Hostname, timezone, locale, users        | Optional Mac App Store applications    |
| Root-owned files and SSH daemon policy   | Optional user dotfiles and preferences |
| System launchd/systemd services          | User services                          |
| System-wide fonts and OS integrations    | Non-privileged configuration           |

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

`maison apply` is deliberately system-first: it activates the Nix system layer and then converges the optional private
user layer. A user-layer failure does not roll back the active Nix generation.

## Repository layout

```text
flake.nix                     system inputs
inventory.toml                neutral starter inventory and schema example
hosts/example-darwin/         neutral example host override
examples/terroir/              private-overlay starter layout
nix/                          OS-level modules and deployment definitions
.mise/tasks/                  Maison framework workflows
scripts/                      bootstrap, validation, and deployment transactions
mise.toml                     repository development tools and task discovery
mise.lock                     locked repository development tool artifacts
dotfiles/pi/extensions/       repository-owned Pi validation workspace
```

The root `mise.toml` contains only tools required to develop and validate Maison. User applications, packages,
preferences, and dotfiles belong in the private overlay. `config/mise/` contains empty public policy stubs so a checkout
without an overlay remains valid; use `examples/terroir/config/mise/` as the starting point for private policy.

## Private overlay

A private overlay mirrors Maison-owned paths such as `inventory.toml`, `hosts/`, `config/mise/`, and `dotfiles/`.
It supplies real users, hosts, deploy targets, tools, applications, preferences, and dotfiles without making them part
of the public framework.

Overlay discovery uses this precedence:

1. `--overlay <git-url-or-path>` for the current bootstrap run.
2. `MAISON_OVERLAY_SOURCE` from the environment or a secrets manager.
3. `${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml`.

The overlay is cloned or updated at `${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay`. Overlay state is local,
owner-only, and never committed. Without an overlay, Maison uses neutral starter data and installs no user applications
or personal packages.

Keep passwords, tokens, SSH private keys, signing private keys, and other secrets in Bitwarden or an equivalent secret
manager. A private Git repository is not a substitute for secret storage.

## Bootstrap behavior

From an existing Maison checkout, `bootstrap.sh` uses that checkout and does not create a second copy under `~/.maison`.
When run outside a checkout, it clones Maison to `~/.maison` by default; set `MAISON_HOME` to override that location.

Bootstrap installs verified pinned mise and Nix/Lix artifacts when missing, trusts the Maison project configuration,
stores or refreshes the overlay source, and runs the Maison bootstrap task. Use `--user-only` on the mise task when
system activation should be skipped. Do not use pipe-to-shell bootstrap examples; verify downloaded bootstrap artifacts
against `bootstrap/artifacts.toml` before execution.

## Deployment and recovery

`maison deploy <host>` requires a clean working tree and transfers committed Maison content only. With a private overlay
active, deployment targeting and Nix evaluation use the overlay inventory while Maison remains the reusable framework.

Repository replacement uses a root-owned transaction boundary and revision-bound rollback. Restricted recovery repairs
only reversible user state; package and application side effects are not rolled back. See the [architecture](docs/architecture.md),
[deployment guide](docs/deployment.md), [recovery guide](docs/recovery.md), and [package policy](docs/package-policy.md).

## Development

Maison uses repository-owned mise tools and dstack/Beads workflow controls:

```bash
mise install --locked
mise run check
uv run scripts/check-docs.py
mise exec -- hk check
```

Use `/plan-features`, `/start-feature <slug>`, `/implement-feature <slug>`, and `/close-feature <slug>` for planned work.
