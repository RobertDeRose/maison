# Add a host

Real hosts belong in the private overlay inventory. Bootstrap or select the overlay first:

```bash
./bootstrap.sh --host "$(hostname -s)" --overlay GIT-URL-OR-PATH
maison host add <hostname> --system aarch64-linux --user operator --profiles base,dev,linux --overrides
```

When an overlay inventory is active, `host:add` writes both `inventory.toml` and optional `hosts/<hostname>/system.nix` to the overlay clone. The active inventory must satisfy the shared schema contract in `schemas/inventory.toml`: supported systems are `aarch64-darwin`, `aarch64-linux`, and `x86_64-linux`; profiles are `base`, `dev`, `mac`, and `linux`; duplicate profiles, unknown feature keys, unknown deploy fields, and wrong value types are rejected.

For a deployable Linux host, add an explicit deployment table to the active `inventory.toml`:

```toml
[hosts.example.deploy]
enable = true
hostname = "example.example.com"
ssh_user = "maison-deploy"
user_ssh_user = "operator"
repo_path = "/home/operator/.maison"
remote_build = false
auto_rollback = true
magic_rollback = true
```

`ssh_user` is the deployment account used for system activation and repository-transaction helper access. It defaults to `maison-deploy` and is separate from the managed user (`user_ssh_user`), which owns the remote repository. For a first deployment to an existing host that does not yet have a reachable `maison-deploy` account, temporarily set `ssh_user` to an existing privileged account for the system deployment, then switch back to `maison-deploy` after the account and sudoers policy exist.

Then run:

```bash
maison host validate
maison system plan --host example
maison system deploy example --dry-activate
```

Host override directories must match an inventory host and may contain only `system.nix`. Host override files may contain OS-level exceptions only. User differences belong in Tera dotfiles or platform mise configuration.
