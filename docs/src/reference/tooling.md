# Tooling reference

## Files

| File                                  | Contract                                                                    |
|---------------------------------------|-----------------------------------------------------------------------------|
| `mise.toml`                           | Declares project tools, environment, and named tasks.                       |
| `mise.lock`                           | Project-owned resolved downloads; commit it.                                |
| `hk.pkl`                              | Defines the shared check/fix/pre-commit step map.                           |
| `.config/rumdl.toml`                  | Configures Markdown linting and deterministic fixes.                        |
| `.editorconfig`                       | Keeps editor output on UTF-8, LF, final newlines, and no trailing spaces.   |
| `_typos.toml`                         | Ignores hash-like identifiers while retaining typo checks elsewhere.        |
| `contextlint.config.json`             | Checks documentation links, anchors, and image targets.                     |
| `cog.toml`                            | Configures Conventional Commits and concise changelogs.                     |
| `.config/cog-changelog.tera`          | Renders plain Markdown changelogs without author noise.                     |
| `scripts/setup-tooling.py`            | Resolves the lock, installs tools, installs hooks, and returns JSON status. |
| `schemas/inventory.toml`              | Shared public inventory schema contract for Python and Nix validators.      |
| `scripts/enable-docs-deployment.py`   | Configures workflow-built Pages through external `gh`.                      |
| `.github/workflows/ci.yml`            | Runs repository checks, platform builds, and bootstrap checks on CI events. |
| `.github/workflows/docs.yml`          | Builds gated docs from the default branch or manual dispatch.               |
| `.github/workflows/cache-refresh.yml` | Warms cache targets and opens or updates flake refresh PRs without merging. |

## Tools

The universal tool set is hk `1.49.0` and the `latest` Cocogitto, Harper CLI, Contextlint, mdBook, uv, rumdl, typos,
and `npm:markdown-table-formatter` releases. Contextlint checks documentation links, anchors, and image
targets. Its reviewed low-download aube exception applies only to `@contextlint/cli`. Both hk Pkl imports use `1.49.0`.
Equivalent native hk steps own matching formatter and linter commands. Independent steps have no explicit `depends`
edges. Go retains two output-sensitive edges: `gofumpt` follows `goimports` so the stricter formatter owns final source,
and fix-only `go-mod` follows `gofumpt` so module metadata observes the final imports.

Custom steps are limited to behavior hk does not provide equivalently: Contextlint must discover its whole-project
configuration without a changed-file argument; documentation and Markdown-table checks are project composites or have
no built-in; rumdl avoids the built-in diff header while discovering `.config/rumdl.toml`; Go, Elixir, and Nix commands
lack matching built-ins; and test, compiler, linter, and module checks must remain gated by their project manifests.

Recorded language profiles: `other`.

## Overlay template

`overlay_template/` is a Copier template for private overlays, not a static directory to copy blindly. Maison bootstrap
runs it with `uvx copier` when the user chooses immediate setup. Manual generation from a Maison checkout is:

```bash
mise install uv
MAISON_HOME="$PWD" MAISON_HOST="$(hostname -s)" \
  mise exec -- uvx --from copier copier copy --trust \
    --data "username=$(id -un)" overlay_template "$HOME/src/my-maison-overlay"
```

Copier initializes the destination Git repository. The first-copy task delegates current-host registration to
Maison's `mise run host:add`, which owns supported-platform detection and inventory validation. `copier update --trust`
updates an existing overlay without rerunning host registration. Keep the generated repository
private and keep secrets in Bitwarden or an equivalent secret manager. Maison persists the active overlay source in
`${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml`; direct Nix and `nh` evaluations pass that checkout as
the explicit `overlay` flake input, so those evaluations remain pure and do not require `--impure`. User convergence
loads the overlay's `config/mise/config.toml` as the global mise layer while the Maison checkout remains the project
layer; without an overlay, public `config/mise` files are used. During convergence, Maison temporarily hides the
installed overlay-backed global config so mise resolves relative dotfile sources from the overlay checkout.

## Template updates

`.copier-answers.yml` records the Copier source and rendered answers for a generated overlay. `copier update --trust`
updates template-owned files while preserving user edits and does not add another host. The Maison repository's own
`.copier-answers.yml` remains separate and records its dstack template channel and source commit.

## Commit messages and changelogs

Changelog-visible `feat`, `fix`, `perf`, and `refactor` commits require a semantic scope. The commit hook also checks
Conventional Commit syntax, grammar, a 72-character subject, 100-character body lines, and canonical optional `Beads:`
footers. Harper uses its full native rule set after filtering Git comments/diffs, canonical release subjects, and a
canonical `Beads:` footer; the other commit validators still inspect the unfiltered message. Internal build, chore, CI,
documentation, release, style, and test commits are omitted from `cog changelog`. Breaking changes render as plain
Markdown.

The generated `cog.toml` initially accepts any syntactically valid scope. To constrain scopes, add a `scopes = ["..."]`
allowlist, document each stable subsystem in README when present or on this page otherwise, and update `AGENTS.md` so
agents apply the same taxonomy. Run `cog check` after changing the allowlist.

No recognized language profile is active; only the universal tooling baseline is
configured.

## Tasks

| Task                     | Behavior                                                                     |
|--------------------------|------------------------------------------------------------------------------|
| `check`                  | Install repository tools, then run data, shell, Python test, and Nix checks. |
| `check:tests`            | Run bounded Python `unittest` discovery across `tests/test_*.py`.            |
| `fix`                    | Apply deterministic hk fixes to the working tree.                            |
| `docs:check`             | Build the book, then validate documentation metadata and navigation.         |
| `docs:build`             | Build the mdBook site.                                                       |
| `docs:deployment:enable` | Configure Pages and enable its repository gate through external `gh`.        |
| `docs:serve`             | Serve mdBook on port 3000 by default or a supplied port.                     |

The committed lock targets `linux-x64`, `linux-arm64`, and `macos-arm64`. Intel macOS and Windows are not part of this
POSIX-shell task contract.

Inventory validation fixtures live under `tests/fixtures/inventory/` and are consumed by both Python tests and Nix
evaluation checks. Add fixture cases when changing inventory fields, defaults, profile compatibility, deploy path rules,
or overlay host override layout.

Python tests are partitioned by subsystem: inventory and overlay behavior, deployment and bootstrap contracts,
migration behavior, ownership boundaries, repository contracts and mutation locking, transaction behavior, configuration
editing, deploy-transaction internals, and shared inventory schema fixtures. External processes in tests must run
through `tests/support/processes.py`, which provides process-group cleanup, stdout/stderr capture, bounded diagnostics,
a 30 second default timeout, and explicit per-call overrides up to 300 seconds. Document any override at the call site.

The mise environment routes hooks through mise with `HK_MISE=1` and sets `GIT_CONFIG_PARAMETERS="'merge.ff=only'"`, so
Git rejects merges that require a merge commit.

The cache-refresh workflow may create or update `automation/refresh-flake-lock` after cache warming, but dependency
approval is not automated. That workflow must not invoke `gh pr merge`, pass `--admin`, enable auto-merge, or otherwise
bypass branch protection.

The universal tool count remains ten; `gh` is an external administrative prerequisite, not a mise tool. Pages requires
`build_type=workflow` plus `DOCS_DEPLOYMENT_ENABLED=true`. The build job has `contents: read`; only the deploy job has
`pages: write` and `id-token: write`.

Provisioning reports separate mise availability, lock, install, and hook states. Overall status is `succeeded`,
`degraded`, or `skipped`; failed or skipped stages include exact recovery commands.
