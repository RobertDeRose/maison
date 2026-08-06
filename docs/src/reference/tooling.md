# Tooling reference

## Files

| File                             | Contract                                                                     |
|----------------------------------|------------------------------------------------------------------------------|
| `mise.toml`                      | Maison development tools, environment, and task discovery.                   |
| `mise.lock`                      | Maison development tool downloads; commit it.                                |
| `hk.pkl`                         | Shared check/fix/pre-commit step map.                                        |
| `.config/rumdl.toml`             | Markdown lint configuration.                                                 |
| `contextlint.config.json`        | Documentation links, anchors, and image targets.                             |
| `scripts/setup-tooling.py`       | Resolves the locked toolchain, installs tools and hooks, and reports status. |
| `schemas/inventory.toml`         | Public inventory schema consumed by Python and Nix validators.               |
| `docs/src/reference/flake.md`    | Public flake outputs, modules, helpers, and checks.                          |
| `docs/src/reference/consumer.md` | Consumer files, root selection, composition, and mutation boundaries.        |
| `.github/workflows/ci.yml`       | Repository checks, platform builds, and bootstrap checks.                    |

## Tools

The universal tool set includes hk `1.49.0`, Cocogitto, Harper CLI, Contextlint, mdBook, uv, rumdl, typos, and the
Markdown table formatter. The committed lock targets `linux-x64`, `linux-arm64`, and `macos-arm64`; Intel macOS and
Windows are outside this POSIX-shell task contract.

Maison uses native hk behavior whenever it matches the required formatter or linter. Tests, compilers, module checks, and
Nix commands remain gated by their project manifests. No recognized language profile is active; only the universal
baseline is configured.

## Consumer boundary

Maison owns its contributor toolchain. A consumer owns `flake.nix`, `flake.lock`, `inventory.toml`, host overrides,
`config/mise/`, dotfiles, and deployment state. Run consumer commands from that checkout or set an explicit root:

```bash
MAISON_HOME="$HOME/.maison" \
MAISON_CONSUMER_ROOT="$HOME/src/terroir" \
maison plan
```

Consumer operations use the consumer flake and lock directly. They do not use Maison's lock as a fallback, do not pass a
a synthetic alternate configuration root, and do not write Maison files. For fresh setup, `bootstrap.sh --setup PATH`
renders the retained `overlay_template/` Copier starter once; Copier is not part of normal runtime operations.

## Tasks

| Task                | Behavior                                                            |
|---------------------|---------------------------------------------------------------------|
| `check`             | Install Maison tools, then run data, shell, Python, and Nix checks. |
| `consumer:validate` | Validate a consumer without activation or provider credentials.     |
| `self:update`       | Upgrade Maison from the selected consumer's pinned input.           |
| `check:tests`       | Run bounded Python unittest discovery across `tests/test_*.py`.     |
| `fix`               | Apply deterministic hk fixes to the working tree.                   |
| `docs:check`        | Build and validate documentation structure.                         |
| `docs:build`        | Build the mdBook site.                                              |
| `docs:serve`        | Serve mdBook on port 3000 or a supplied port.                       |

`consumer:validate` is the mise task behind `maison consumer validate`; it owns the framework-side contract so a
consumer does not need a duplicate validation suite. `self:update` is the transactional framework upgrade path: it
updates the consumer's Maison input, validates with the candidate CLI, and rolls back the consumer lock and local CLI
state together when any step fails. Inventory fixtures live under `tests/fixtures/inventory/` and are
consumed by Python tests and Nix evaluation checks. Add fixtures when changing schema fields, defaults, profile
compatibility, deployment path rules, or host override layout.

### Hidden integration-test tasks

Platform integration tasks are Mise-only and are hidden from `maison` resolution, help, completion, and task listings.
Use `mise -C "$MAISON_HOME" tasks --hidden` for discovery and invoke a task directly when deliberately running
integration infrastructure. The public CLI cannot expose hidden tasks through flags such as `maison tasks --hidden`.

The host-side Lume prerequisite is pinned to Trycua CUA release `lume-v0.5.1` and archive
`lume-0.5.1-darwin-arm64.tar.gz` at
`https://github.com/trycua/cua/releases/download/lume-v0.5.1/lume-0.5.1-darwin-arm64.tar.gz`, with SHA-256
`7f10cfbe66a800f98a5db88129f7dc024600fcdc139e0be124845bc7a3dc1359`. On Apple Silicon macOS 13 or newer,
`test:lume:install` verifies the archive and version, then atomically installs its top-level `lume` executable at
`${XDG_DATA_HOME:-$HOME/.local/share}/maison/lume/0.5.1/lume`. The install is user-owned, idempotent, serialized for
concurrent callers, and refuses to replace an incompatible version. No privileged package installation, global PATH
mutation, launch agent, or upstream shell installer is used.

Python tests are partitioned by inventory, consumer repository, deployment/bootstrap, migration, ownership, repository
mutation, transaction, configuration editing, deploy transaction, and user convergence behavior. External processes use
`tests/support/processes.py`, which supplies process-group cleanup, bounded diagnostics, and a 30-second default timeout.

The mise environment routes hooks through mise with `HK_MISE=1` and sets `GIT_CONFIG_PARAMETERS="'merge.ff=only'"`, so
Git rejects merges that require a merge commit.

## Documentation and releases

`contextlint` validates documentation links and anchors. The cache-refresh workflow may update Maison's own `flake.lock`,
warm cache targets, and open a review PR; it must not merge or bypass branch protection. The project `.copier-answers.yml`
records the dstack scaffold provenance for Maison itself; it is not a consumer configuration mechanism.

Pages requires `build_type=workflow` plus `DOCS_DEPLOYMENT_ENABLED=true`. The build job has `contents: read`; only the
deploy job has `pages: write` and `id-token: write`.
