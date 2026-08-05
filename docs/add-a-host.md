# Add a host

Real hosts belong in the consumer repository's `inventory.toml`. Select the consumer explicitly or run from its Git
checkout:

```bash
export MAISON_HOME="$HOME/.maison"
export MAISON_CONSUMER_ROOT="$HOME/src/terroir"
maison host add "$(hostname -s)" --user "$(id -un)"
```

`host:add` writes the consumer inventory and, when requested, an optional `hosts/<hostname>/system.nix` override. It
requires a Git authoring checkout, validates the candidate inventory before replacement, and refuses to use Maison's
neutral inventory as a mutation target.

The inventory must satisfy the shared schema in `schemas/inventory.toml`: supported systems are `aarch64-darwin`,
`aarch64-linux`, and `x86_64-linux`; profiles are `base`, `dev`, `mac`, and `linux`. Duplicate profiles, unknown
feature keys, unknown deploy fields, and wrong value types are rejected.

For a deployable Linux host, add an explicit deployment table to the consumer `inventory.toml`:

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

Then validate and preview without activation:

```bash
maison host validate
maison system plan --host example
maison system deploy example --dry-activate
```

Host override directories must match an inventory host and may contain only `system.nix`. Host override files contain
OS-level exceptions; user differences belong in consumer mise configuration or dotfiles.
