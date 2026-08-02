# Maison

Maison is a reusable two-layer macOS and Linux configuration framework:

- **Nix/Lix owns operating-system state.** nix-darwin configures Apple Silicon macOS; system-manager configures supported non-NixOS Linux.
- **mise owns optional user state.** A private overlay can provide tools, packages, applications, preferences, and dotfiles.

Home Manager is intentionally absent. `nh` provides the local nix-darwin workflow, while `deploy-rs` handles remote
system-manager profiles and connection-aware system rollback.

Maison is intentionally generic. It contains framework code, neutral examples, tests, and bootstrap tooling—not a
maintainer's personal application list or dotfiles.

## Quick start

Clone Maison and bootstrap with an existing private overlay:

```bash
git clone https://github.com/RobertDeRose/maison.git
cd maison
MAISON_OVERLAY=git@github.com:OWNER/my-maison-overlay.git \
  ./bootstrap.sh --host "$(hostname -s)"
```

If no overlay is supplied, bootstrap asks whether to create one now with the Copier template. Answer **yes** to
create `${MAISON_OVERLAY_HOME:-$HOME/src/maison-overlay}`, collect the private inventory identity, and automatically
register the current supported macOS or Linux host through `mise run host:add`. Answer **no** to install only Maison
and its CLI; system and user activation are skipped, and bootstrap prints the documentation path for completing setup.

You can also create an overlay explicitly from an existing Maison checkout:

```bash
mise install uv
MAISON_HOME="$PWD" MAISON_HOST="$(hostname -s)" \
  mise exec -- uvx --from copier copier copy --trust \
    examples/terroir "$HOME/src/my-maison-overlay"
```

The overlay repository can use any name, hosting service, or access model. Commit it and rerun bootstrap with
`--overlay <git-url-or-path>` or `MAISON_OVERLAY=<git-url-or-path>` before the first real switch:

```bash
./bootstrap.sh --host "$(hostname -s)" --overlay "$HOME/src/my-maison-overlay"
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
examples/terroir/              Copier template for private overlays
nix/                          OS-level modules and deployment definitions
.mise/tasks/                  Maison framework workflows
scripts/                      bootstrap, validation, and deployment transactions
mise.toml                     repository development tools and task discovery
mise.lock                     locked repository development tool artifacts
dotfiles/pi/extensions/       repository-owned Pi validation workspace
```

The root `mise.toml` contains only tools required to develop and validate Maison. User applications, packages,
preferences, and dotfiles belong in the private overlay. `config/mise/` contains empty public policy stubs so a checkout
without an overlay remains valid; use the `examples/terroir` Copier template for private policy.

## Private overlay

A private overlay mirrors Maison-owned paths such as `inventory.toml`, `hosts/`, `config/mise/`, and `dotfiles/`.
The Copier template in `examples/terroir/` supplies that layout and registers the current host through Maison's
validated `host:add` task. The overlay owns real users, hosts, deploy targets, tools, applications, preferences, and
dotfiles without making them part of the public framework.

Overlay discovery uses this precedence:

1. `--overlay <git-url-or-path>` for the current bootstrap run.
2. `MAISON_OVERLAY=<git-url-or-path>`.
3. `MAISON_OVERLAY_SOURCE=<git-url-or-path>` as a legacy compatibility fallback.
4. `${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml`.

An existing local Git repository is used directly. A remote Git URL is cloned or updated at
`${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay`. Overlay state is local, owner-only, and never committed.
Without an overlay, first-run bootstrap does not install Nix or activate neutral starter data.

Keep passwords, tokens, SSH private keys, signing private keys, and other secrets in Bitwarden or an equivalent secret
manager. A private Git repository is not a substitute for secret storage.

## Bootstrap behavior

From an existing Maison checkout, `bootstrap.sh` uses that checkout and does not create a second copy under `~/.maison`.
When run outside a checkout, it clones Maison to `~/.maison` by default; set `MAISON_HOME` to override that location.

Bootstrap first installs verified pinned mise, links the `maison` CLI, and trusts the Maison project configuration. It
then resolves `--overlay`, `MAISON_OVERLAY`, legacy `MAISON_OVERLAY_SOURCE`, or saved state. If none is available, an
interactive run offers Copier setup; declining (or a non-interactive run without `MAISON_REQUIRE_OVERLAY=true`) exits
without installing Nix or activating system/user state. Once an overlay exists, bootstrap stores or refreshes its state,
installs verified Nix/Lix artifacts when missing, and runs the Maison bootstrap task. Use `--user-only` on the mise task
when system activation should be skipped. Do not use pipe-to-shell bootstrap examples; verify downloaded bootstrap
artifacts against `bootstrap/artifacts.toml` before execution.

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
