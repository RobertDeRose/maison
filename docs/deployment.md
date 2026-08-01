# Remote deployment

The canonical source pair is the public Maison framework plus a private overlay selected by the operator. Linux
deployment is intentionally split into a deploy-rs system transaction and a Maison repository/user transaction. The
archived source repository is historical recovery material, not a deployment source.

## System only

```bash
maison system deploy example-linux
maison system deploy example-linux --dry-activate
```

This invokes deploy-rs against `deploy.nodes.example-linux.profiles.system`. The closure is placed in `/nix/var/nix/profiles/system-manager-profiles/system-manager` and activated as root. Linux deployment requires systemd and verifies the active hostname, timezone/localtime, SSH configuration/reload, and Maison-managed service units as part of system activation. Schema, activation-path, and dry-activation checks are built in CI.

## System and user

```bash
maison deploy example-linux
```

Before system deployment starts, Maison requires a clean working tree and builds a source archive from committed Git content only. The archive contains `.maison-revision` but never `.git`, dirty changes, untracked files, ignored files, or local credentials. The resulting remote tree is a deployed runtime snapshot, not an authoring checkout; repository-writing commands must be run from the public source checkout or the private overlay repository instead. If a private overlay inventory is active, deployment targeting and Nix evaluation use that overlay inventory while the public Maison archive remains the reusable vehicle code.

After successful system activation, Maison:

1. Uploads the archive separately from the remote command stream.
2. Validates that `repo_path` is a normalized descendant of the managed user's home.
3. Allocates a root-owned transaction root on the same filesystem outside any managed-user-writable ancestor.
4. Creates an unpredictable transaction ID, acquires the repository transaction lock, and journals each privileged step.
5. Performs startup recovery of any incomplete repository transaction before proceeding.
6. Stages the new source tree and rollback source under the root-owned transaction root.
7. Records expected old/new revisions before finalize.
8. Runs full `user:apply` as the managed user from the staged repository.
9. If user convergence fails, rolls back the repository and verifies the restored prior revision before continuing.
10. On user-convergence failure, runs restricted recovery as the managed user from the restored repository.
11. Finalizes or rolls back by reading the root-owned journal and refusing unsafe ownership, symlink, permission, or cross-filesystem state.

Restricted recovery repairs dotfiles, mise lock links, non-package mise user state, and Maison-owned finalization. It does
not rerun package/app convergence, application-backup migration, legacy Git migration, system activation, or Nix
rollback. Recovery honors an explicitly supplied `--force-dotfiles` flag but never enables it implicitly. A successful
or failed recovery writes a mode-0600 JSON diagnostic under `~/.local/state/maison/recovery/`; the original user
convergence failure remains the deployment exit status.

For the default `/home/<user>/.maison` repository path, the default transaction namespace is a root-owned sibling under `/home`, such as `/home/.maison-deploy/transactions/<user>/<repo-hash>/`. Maison fails closed when no same-filesystem root-owned transaction root exists outside the managed user's control.

Remote system and repository actions now run through a separate deployment SSH account (default `maison-deploy`). Sudo access for that account is command-scoped and argument-bounded for `deploy`-related activation and Maison transaction helpers.

Existing hosts that do not yet have a reachable `maison-deploy` account need one bootstrap deployment through an explicitly configured privileged account, such as `ssh_user = "root"`. After that system deployment creates the deployment account and sudoers policy, switch the inventory back to the `maison-deploy` default.

When the remote managed user does not yet have mise, the user-convergence fallback reads `bootstrap/artifacts.toml` from the staged repository, downloads the pinned mise artifact to disk, verifies its SHA-256 digest, and installs only the verified local binary. Use `--system-only` to skip repository transfer and user convergence.

## Overlay inventory

Put real deployment endpoints in Terroir's private `inventory.toml`. Public Maison keeps only neutral examples. The
Terroir source is discovered from `--overlay`, `MAISON_OVERLAY_SOURCE`, or the saved XDG state record, and the clone lives
under `${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay`.

## Inventory fields

```toml
[hosts.example-linux.deploy]
enable = true
hostname = "example-linux.example.invalid"
ssh_user = "maison-deploy"
user_ssh_user = "operator"
repo_path = "/home/operator/.maison"
remote_build = false
auto_rollback = true
magic_rollback = true
```

`ssh_user` activates the system with deployment privileges. `user_ssh_user` must equal the managed inventory username. `repo_path` must be below `/home/<user>`; `/`, `/home`, the user's home itself, non-normalized paths, and traversal are rejected by both Python and Nix validation. Deployment keys, defaults, and value types are defined in the shared public schema contract at `schemas/inventory.toml`, and shared fixtures keep Python and Nix validation behavior aligned.

## Migration and archive boundary

The validation gate must pass before archiving any source repository. The public Maison framework and selected private
overlay are the active source pair; archived source history remains recovery material. Keep the source checkout and migration backups
available until the new topology has been exercised successfully; archiving does not delete local recovery data.

## Safety boundary

Deploy-rs rollback covers the system profile. Repository rollback covers the source tree used for subsequent user
convergence and recovery. Repository transaction state is privileged state: the managed user must not be able to unlink,
replace, or edit journals, staging trees, rollback trees, or locks. Mise changes that completed before a later user-step
failure are convergent state, not a Nix generation. Restricted recovery repairs the reversible user-owned portion;
package/app operations are not rolled back and are recorded as follow-up side effects in the diagnostic report.
