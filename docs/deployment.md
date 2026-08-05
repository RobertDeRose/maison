# Remote deployment

The consumer repository is the deployment source. Maison supplies the reusable modules, CLI, transaction helpers, and
runtime artifacts; it is never the personal deployment root.

## System only

```bash
maison system deploy example-linux
maison system deploy example-linux --dry-activate
```

This invokes deploy-rs against the consumer's `deploy.nodes.example-linux.profiles.system`. The closure is activated as
root under `/nix/var/nix/profiles/system-manager-profiles/system-manager`. Linux deployment verifies systemd, hostname,
timezone, SSH configuration, and Maison-managed service units.

## System and user

```bash
maison deploy example-linux
```

Deployment requires a clean consumer working tree and creates an archive from committed consumer content only. The archive
contains `.maison-revision`, but never `.git`, dirty changes, untracked files, ignored files, or local credentials. The
remote tree is a runtime snapshot, not an authoring checkout.

The privileged extractor bounds the uploaded archive at 256 MiB compressed, 4,096 members, 64 MiB per member, and 256
MiB total expanded regular-file content. It validates and extracts members incrementally and rejects traversal, symlink,
and special-file entries.

After system activation, Maison:

1. uploads the committed consumer archive;
2. validates the managed-user repository path;
3. allocates a root-owned transaction root on the same filesystem;
4. recovers incomplete transaction state;
5. stages the new consumer tree and rollback source;
6. records expected revisions and runs user convergence as the managed user;
7. restores and verifies the prior consumer revision after user failure;
8. runs restricted recovery from the restored consumer; and
9. finalizes or rolls back from the root-owned journal.

Restricted recovery repairs reversible dotfiles, mise lock links, non-package mise state, and finalization. It does not
rerun package/application convergence, application-backup migration, system activation, or Nix rollback. Recovery writes
a mode-0600 diagnostic under `~/.local/state/maison/recovery/`; the original convergence failure remains the deployment
exit status.

Remote system and repository actions use the separate deployment SSH account configured by the consumer inventory (usually
`maison-deploy`). Sudo access is command-scoped and argument-bounded for deploy activation and Maison transaction helpers.

When the remote managed user lacks mise, the fallback reads `bootstrap/artifacts.toml` from the Maison runtime, verifies
the pinned artifact digest, and installs only that binary. Use `--system-only` to skip repository transfer and user
convergence.

## Inventory fields

Real endpoints belong in the consumer `inventory.toml`:

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

`ssh_user` activates the system with deployment privileges. `user_ssh_user` must equal the managed inventory username.
`repo_path` must be a normalized descendant of `/home/<user>`; both Python and Nix validation reject traversal and unsafe
paths. Deployment keys and field types are defined by `schemas/inventory.toml`.

## Safety boundary

Deploy-rs rollback covers the system profile. Repository rollback covers the consumer tree used for subsequent user
convergence and recovery. Privileged transaction state is inaccessible to the managed user. Mise changes completed before
a later user-step failure are convergent state, not a Nix generation; package/application side effects remain recorded
follow-up work.
