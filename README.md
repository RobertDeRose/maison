# Maison

Maison is a reusable two-layer macOS and Linux configuration framework:

- **Nix/Lix owns operating-system state.** nix-darwin configures Apple Silicon macOS; system-manager configures supported non-NixOS Linux.
- **mise owns optional user state.** A private overlay can provide tools, packages, applications, preferences, and dotfiles.

Home Manager is intentionally absent. `nh` provides the local nix-darwin workflow, while `deploy-rs` handles remote
system-manager profiles and connection-aware system rollback.

Maison is intentionally generic. It contains framework code, neutral examples, tests, and bootstrap tooling—not a
maintainer's personal application list or dotfiles.

## Quickstart

Choose one of these installation paths.

### 1. Install with curl and create an overlay during setup

This downloads the reviewed bootstrap script to a temporary file instead of piping remote code to a shell. Run it
without an overlay, answer **yes** when prompted, and complete the Copier questions:

```bash
curl -fsSL https://raw.githubusercontent.com/RobertDeRose/maison/main/bootstrap.sh | bash
```

Maison clones itself to `~/.maison` by default. New Copier overlays and remote overlays use
`${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay` by default; set `MAISON_OVERLAY_HOME` to override the Copier
destination. Bootstrap registers the current host.

### 2. Install with curl and use an existing overlay

Set `MAISON_OVERLAY` to a local checkout or a remote Git repository. Bootstrap uses it directly when local and clones
remote sources into Maison's overlay data directory:

```bash
curl -fsSL https://raw.githubusercontent.com/RobertDeRose/maison/main/bootstrap.sh \
  | bash -s -- --overlay "git@github.com:OWNER/my-maison-overlay.git"
```

The `--overlay <git-url-or-path>` option is equivalent and takes precedence over `MAISON_OVERLAY`.

### 3. Clone Maison and run Copier manually

Use this when you want to inspect or customize the overlay before bootstrap:

```bash
git clone https://github.com/RobertDeRose/maison.git
cd maison
mise install uv
MAISON_HOME="$PWD" MAISON_HOST="$(hostname -s)" \
  mise exec -- uvx --from copier copier copy --trust \
    --data "username=$(id -un)" overlay_template "$HOME/src/my-maison-overlay"

./bootstrap.sh --host "$(hostname -s)" --overlay "$HOME/src/my-maison-overlay"
```

Copier asks for the remaining inventory identity values, initializes the destination as a Git repository, and runs
its first-copy host task. Commit and publish the private overlay according to your own repository workflow.

## Supported systems

- `aarch64-darwin`
- `aarch64-linux`
- `x86_64-linux`

Intel macOS is deliberately unsupported rather than partially configured.

## Private overlay

A private overlay mirrors Maison-owned paths such as `inventory.toml`, `hosts/`, `config/mise/`, and `dotfiles/`.
The `overlay_template/` Copier template supplies that layout and registers the current host through Maison's
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

## Common commands

```bash
maison doctor
maison plan
maison apply
maison status
maison publish
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

`maison status` and `maison publish` inspect and publish only the active private overlay. Status fetches when possible
and reports clean/dirty, ahead/behind/diverged, no-upstream, and last-known/offline states without claiming a stale
checkout is synchronized. Publish uses the configured upstream, refuses unsafe history before stashing, preserves
tracked and untracked work while leaving ignored files untouched, and restores the stash after pushing. It does not
create commits for arbitrary edits.

Software add/remove commands also require the active private overlay. They refresh it fast-forward-only before editing,
reject dirty declaration or lock targets, preserve unrelated work, and create focused commits only after successful
transactions. Commit failures leave validated files in place for manual recovery; public Maison is never the mutation
fallback.

`maison apply` is deliberately system-first: it activates the Nix system layer and then converges the optional private
user layer. A user-layer failure does not roll back the active Nix generation.

## Deployment and recovery

`maison deploy <host>` requires a clean working tree and transfers committed Maison content only. With a private overlay
active, deployment targeting and Nix evaluation use the overlay inventory while Maison remains the reusable framework.

Repository replacement uses a root-owned transaction boundary and revision-bound rollback. Restricted recovery repairs
only reversible user state; package and application side effects are not rolled back. See the [architecture](docs/architecture.md),
[deployment guide](docs/deployment.md), [recovery guide](docs/recovery.md), and [package policy](docs/package-policy.md).

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

## Repository layout

```text
flake.nix                         system inputs
inventory.toml                    neutral starter inventory and schema example
hosts/example-darwin/             neutral example host override
overlay_template/                 Copier template for private overlays
nix/                              OS-level modules and deployment definitions
.mise/tasks/                      Maison framework workflows
scripts/                          bootstrap, validation, and deployment transactions
mise.toml                         repository development tools and task discovery
mise.lock                         locked repository development tool artifacts
dotfiles/pi/settings.defaults.json  public Pi settings defaults; personal extensions stay in Terroir
```

The root `mise.toml` contains only tools required to develop and validate Maison. User applications, packages,
preferences, and dotfiles belong in the private overlay. `config/mise/` contains empty public policy stubs so a checkout
without an overlay remains valid; use the `overlay_template` Copier template for private policy. Personal Pi extensions
and their validation workspace are maintained privately in Terroir.

## Development

Maison uses repository-owned mise tools and dstack/Beads workflow controls:

```bash
mise install --locked
mise run check
uv run scripts/check-docs.py
mise exec -- hk check
```

Use `/plan-features`, `/start-feature <slug>`, `/implement-feature <slug>`, and `/close-feature <slug>` for planned work.
