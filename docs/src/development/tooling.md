# Developer tooling

This page applies to the public Maison framework repository. Maison uses dstack/Copier controls and Beads for project
lifecycle work. Consumer repositories are plain Git configuration roots: they own their flake, lock, inventory, host
configuration, mise policy, and dotfiles, but do not need to install Maison's contributor workflow.

The repository uses mise to provide project tools and named tasks. Install mise, then run:

```bash
mise install --locked
```

The project toolchain includes Python 3.13.14. Bootstrap installs and activates that locked runtime with
`mise exec --locked python`, so its Python helpers do not depend on the host Python installation. Use the same
explicit runtime for direct Python commands:

```bash
mise exec --locked python -- python -m unittest -v tests.test_inventory_behavior
```

Use the same commands locally and in automation:

```bash
mise run check
mise run check:tests
mise exec --locked python -- python -m unittest -v tests.test_inventory_behavior
mise exec --locked python -- python -m unittest -v tests.test_deployment_contracts
mise exec --locked python -- python -m unittest -v tests.test_migration_behavior
mise exec --locked python -- python -m unittest -v tests.test_ownership_boundary
mise exec --locked python -- python -m unittest -v tests.test_repository_contracts tests.test_repository_mutation
mise exec --locked python -- python -m unittest -v tests.test_transaction_behavior
mise run fix
mise run docs:check
mise run docs:build
mise run docs:deployment:enable
mise run docs:serve
```

Use `/update-project` for the recorded template channel, or `/update-project --stable` / `--unstable` to change it. The
update always records the exact resolved template commit.

`check` is read-only. `fix` changes the working tree. Contextlint checks links, anchors, and image targets across README
and `docs/**/*.md`. The pre-commit hook may fix files while safely stashing unrelated unstaged work. The commit-message
hook enforces Conventional Commits, required scopes for changelog-visible changes, grammar, 72/100-character line
limits, and canonical optional `Beads:` footers. Harper applies its full native rule set to human-authored text after
filtering Git comments/diffs, canonical release subjects, and the canonical machine-readable footer. Run `cog changelog`
to preview the concise user-facing changelog. The hk policy uses native built-in steps whenever their behavior matches;
hk's file locking coordinates independent steps. No dependency chain serializes unrelated checks. Go projects retain
two output-sensitive edges: `gofumpt` follows `goimports`, then fix-only module tidy observes the final imports.

No recognized language profile is active; only the universal tooling baseline
runs.

Pi extensions are personal consumer content and are maintained in the private Terroir repository. Maison does not
install or validate those runtime extensions.

The Python regression suite is split by subsystem. `check:tests` runs `unittest` discovery across every
`tests/test_*.py` file and is expected to complete within five minutes on a warm supported development checkout. Use the
focused commands above while editing a subsystem, then run `mise -E dev run check` once before committing broad or shared
test changes.

Tests that execute external commands use the shared helper in `tests/support/processes.py`. It defaults to a 30 second
timeout, starts commands in an isolated process group where supported, terminates the group on timeout, captures stdout
and stderr, and truncates failure diagnostics. Longer timeouts must be explicit, documented at the call site, and no
longer than 300 seconds.

Maison's TOML mutation helper uses a pinned `tomlkit` wheel checked in under `.mise/vendor/`. The helper verifies the
wheel digest before importing it, so configuration repair commands still work when normal mise project tool resolution
is skipped or broken and do not depend on ambient Python site-packages.

## GitHub validation

`.github/workflows/ci.yml` runs on every push to `main` and pull request. Its `repository-checks` job installs Nix,
isolates user-global mise configuration, installs the committed tools, and runs `mise run check`. The same workflow
also builds supported platform outputs and exercises the pre-mise bootstrap boundary.

`.github/workflows/cache-refresh.yml` is dependency-update automation, not an approval path. It may refresh `flake.lock`,
build cache targets, push or update the `automation/refresh-flake-lock` branch, open or edit the matching pull request,
and run the reusable hk and CI workflows against that branch. It must leave the pull request open for ordinary review
and branch protection; it must not run `gh pr merge`, use `--admin`, or enable auto-merge.

The consumer is selected locally with `--consumer` during bootstrap, `MAISON_CONSUMER_ROOT`, or the current consumer
Git checkout. Consumer files and locks are ordinary Git state and are never copied into Maison. Do not commit consumer
contents or Bitwarden material to Maison while running development checks.

## Consumer validation

Consumers can run the Maison-owned contract without adding a second test suite:

```bash
maison consumer validate --consumer /path/to/consumer
```

The read-only check validates the consumer flake and lock, inventory, supported systems, mise package and dotfile
configuration, fnox references, documentation links, and raw credential/private-key boundaries. It evaluates expected
Nix outputs without activation or lock updates, and the validator itself never invokes fnox providers; provider
credentials are therefore not needed by the validation contract in CI. `maison self update` uses this same command
through the candidate Maison package after changing only the consumer's Maison input, so failed framework upgrades can
restore the prior lock and local CLI state without touching Maison's own checkout lock.

## Hooks and recovery

Setup installs repository-local hk hooks when the destination is a Git repository. To restore tooling after an offline
or degraded setup, run:

```bash
python3 scripts/setup-tooling.py --json
```

The command gives lock, install, and hook stages one temporary `MISE_CONFIG_DIR`, removes inherited global config
overrides, and deletes the temporary directory on exit. It preserves the scaffold on failure, reports the failed stage,
and uses the same command above for recovery. A repository created without Git can install hooks after Git initialization
with:

```bash
python3 scripts/setup-tooling.py --json
```
