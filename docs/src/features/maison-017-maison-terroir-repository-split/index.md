# MAISON-017: Maison/Terroir repository split

## Delivery Summary

- Beads feature root: `maison-mol-jfhs`
- Status: delivered
- Pull request: none; direct fast-forward merge authorized
- Merge commit: none; delivery uses a fast-forward merge into `dev`
- Design record: [design.md](design.md)

## Delivered Capability

Maison is now split into a reusable public framework and a private site overlay:

- [RobertDeRose/maison](https://github.com/RobertDeRose/maison) is the public dstack-managed framework.
- [RobertDeRose/terroir](https://github.com/RobertDeRose/terroir) is the private plain-Git overlay for inventory, hosts,
  personal/site mise policy, dotfiles, and trusted non-secret configuration.
- [RobertDeRose/nix-config](https://github.com/RobertDeRose/nix-config) is private and archived as the historical source.
- Bitwarden remains the source of truth for secrets and private keys.

Each new repository has a fresh logical history. iTerm2 was explicitly excluded because it is being abandoned; no iTerm2
artifacts were migrated to either new repository.

## User-Facing Behavior

Clone Maison and provide Terroir as the overlay for a real host:

```bash
git clone https://github.com/RobertDeRose/maison.git
cd maison
./bootstrap.sh --host "$(hostname -s)" --overlay git@github.com:RobertDeRose/terroir.git
```

Maison stores the selected source in the owner-only local state file
`${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml` and clones Terroir under
`${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay`. The overlay state is machine-local and is never committed.

## Design Integration

The split preserves the existing ownership boundary: Nix/Lix owns privileged operating-system state and mise owns the
user layer. Maison retains dstack/Copier/Beads controls, validation, tests, Nix modules, neutral examples, and task
machinery. Terroir remains ordinary Git data/configuration rather than a second framework project. Public Maison contains
no personal infrastructure identity, private keys, or secret values.

## Operational Impact

- Real deployment endpoints, users, host overrides, package policy, and personal dotfiles are loaded from Terroir.
- Public Maison remains usable with its neutral starter inventory when no overlay is supplied.
- The archived source repository and owner-only migration manifest remain recovery references.
- No system activation was performed during migration; systemd-backed host integration remains an operational concern for
  the target hosts rather than a migration prerequisite.

## Reference and Contracts

- [Maison overview](../../introduction/project-overview.md)
- [Architecture](../../architecture.md)
- [Remote deployment](../../deployment.md)
- [Operations](../../operations.md)
- [Recovery](../../recovery.md)
- [Migration contract](../../migration-contract.md)
- [Inventory reference](../../reference/inventory.md)
- [Development tooling](../../development/tooling.md)

## Validation Evidence

- `python3 scripts/setup-tooling.py --json` succeeded in a fresh Maison remote clone.
- `uv run scripts/check-docs.py`, `mdbook build docs`, `mise x -- hk check`, and shell validation passed in Maison.
- Terroir inventory validation passed against the shared Maison schema.
- Terroir's private Pi workspace passed `mise run check`: `tsc --noEmit` and 10 focused behavioral tests.
- Local and remote overlay preparation passed; saved overlay state is mode `0600` and `host:list` / `host:validate`
  resolve the Terroir inventory.
- GitHub checks verified Maison public/unarchived, Terroir private/unarchived, and nix-config private/archived, all with
  `main` as the default branch.
- Fresh-history checks found one root per new repository and no shared ancestry with nix-config.
- Published-object privacy scans found no private-key markers, workstation paths, or abandoned iTerm2 artifacts in Maison;
  Terroir contains no raw secrets or private keys.
- No system activation or source-history rewrite occurred during delivery. Maison history was later normalized and signed
  under the repository's current authorship policy.

## Design Reconciliation

### Delivered as Designed

- Manifest approval preceded private copying, public replacement, publication, and archival.
- New repositories were created from fresh histories without importing nix-config commits, refs, or Beads metadata.
- Maison remains public and dstack-managed; Terroir remains private and plain Git.
- The original repository was archived only after validation passed.

### Intentional Changes

- iTerm2 support, preferences, package declarations, workflows, and export tooling were omitted after the user confirmed
  iTerm2 would be abandoned.
- Workstation-specific paths were removed from public migration documentation and replaced with neutral placeholders.

### Post-delivery Reconciliation

- Ported the persistent `nix-hex-box` builder fixes that were mistakenly committed to the archived source after delivery.
- Restored the approved historical Linux host and its personal identity in private Terroir.
- Restored automatic validation for the private Pi TypeScript workspace and its focused tests.
- Restored the private OpenCode ownership note without reintroducing excluded terminal-multiplexer scope.

### Deferred Work

- No real-host system activation or systemd VM integration was available or required for this repository migration.
- Host rollout and later removal of local recovery backups remain operational follow-up after the new topology is exercised.

### Rejected or Removed Scope

- Secrets, passwords, tokens, SSH private keys, and signing private keys remain in Bitwarden rather than either repository.
- Legacy implementation paths, source history, and excluded historical artifacts were not copied into Maison or Terroir.

## Documentation Updated

- `README.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/operations.md`
- `docs/recovery.md`
- `docs/migration-contract.md`
- `docs/src/introduction/project-overview.md`
- `docs/src/reference/inventory.md`
- `docs/src/development/tooling.md`
- `docs/src/planned-features.md`
- `docs/src/features/index.md`
- `docs/src/SUMMARY.md`
- This implemented feature record

## Audit Trail

- Manifest: `${XDG_STATE_HOME:-$HOME/.local/state}/maison/maison-017/manifest.toml`, owner-only mode `0600`,
  explicitly approved and amended to exclude iTerm2.
- Implementation children: `maison-mol-ieqc.1` through `.6`, all closed in dependency order.
- Current signed Maison content commits: `8300ed926ae785e05fe4ddd81c213f69edfac98c`,
  `12455ed8ea6bea981fdaef561a88e7037b8469e1`, and
  `774a602a1efc7e836bf14ba7dbe7d4afa652d4f8`.
- Current signed Terroir content commits: `bfc6dc9b71b99dea1a0b4d4a5a38c16acb74a5ce`,
  `e655386928ec315286fc448bdc4a006c6b5160f3`, and
  `97a4b41ebc7d57d04acbb759e4e7e10e999709c8`.
- Source planning/design commits: `43e5fada1b0b88c3d7e33bd2e82057fa83a7f7aa` and
  `4ba83d44a31afdd909635650f4db42e76a980d93`.
