# Consumer repository reference

A consumer repository is the execution, configuration, and lock root for Maison. It owns the files that describe one
installation; Maison supplies reusable orchestration and framework code.

## Required files

| Path             | Owner    | Purpose                                        |
|------------------|----------|------------------------------------------------|
| `flake.nix`      | Consumer | Host outputs and the Maison flake input        |
| `flake.lock`     | Consumer | Pinned inputs for that consumer                |
| `inventory.toml` | Consumer | Users, hosts, profiles, and deployment targets |
| `README.md`      | Consumer | Maison relationship and consumer usage         |

A consumer may also own `hosts/`, `config/mise/`, `dotfiles/`, and any host-specific Nix modules. The inventory and configuration paths are interpreted relative to the consumer root. If the consumer declares
runtime secrets, its root `fnox.toml` is validated under the [fnox contract](./fnox.md).

## Fresh setup

The maintained `overlay_template/` directory is a Copier starter for fresh consumers; its historical overlay name does
not change the ownership model. Use the verified bootstrap script to render and initialize one:

```bash
./bootstrap.sh --setup "$HOME/src/terroir"
```

Bootstrap registers the current host through Maison's validated `host:add` task, creates the consumer `flake.lock`, and
stops before activation. Review the generated files, create the consumer's first Git commit, and rerun bootstrap with
`--consumer`. Copier is not required for normal runtime commands, and Maison does not save or manage the generated
consumer path.

## Root selection

Commands use the first available value:

1. `MAISON_CONSUMER_ROOT`;
2. `MAISON_REPOSITORY` or `MAISON_REPO`;
3. the Git checkout containing the current working directory, when it is not the Maison installation.

The selected path must contain regular files named `flake.nix`, `flake.lock`, and `inventory.toml`, and must be a separate
checkout rather than Maison or a path nested inside it. Packaged or explicitly configured invocations reject Maison's own
checkout as the consumer. Use an absolute path in automation:

```bash
MAISON_HOME="$HOME/.maison" \
MAISON_CONSUMER_ROOT="$HOME/src/terroir" \
maison plan --host laptop
```

## Flake composition

Consumers pin Maison and compose their own outputs. Maison's public `lib`, modules, schema, and fixtures are reusable
inputs; Maison does not supply personal identity, topology, deployment endpoints, or a consumer lock.

The framework CLI targets consumer installables such as `darwinConfigurations.<host>` and
`systemConfigs.<host>`. A consumer may expose additional aliases, but it must keep those outputs in its own flake.

## Maison validation

Run the read-only contract before activation or after changing the consumer lock:

```bash
maison consumer validate --consumer /path/to/consumer
```

The validator checks the Maison lock input, inventory and supported systems, Nix host outputs, mise package and dotfile
declarations, documentation links, fnox references, and raw credential/private-key boundaries. It runs check-only Nix
evaluation, never activates a system or updates a lock file, and does not invoke fnox providers or require their
credentials. Provider selection remains consumer-owned.

## Mutation boundaries

`plan` is read-only with respect to the consumer repository. `apply`, `update`, host authoring, software authoring,
deployment, and recovery operate on the selected consumer. `maison update` replaces only the consumer's `flake.lock`;
Maison's lock is never an implicit fallback. Consumer Git operations remain outside Maison.

`maison self update` is the focused framework upgrade. It updates only the Maison input, builds the candidate CLI from
the resulting consumer lock, runs `maison consumer validate` through that candidate, and records its executable in
owner-only local CLI state. A failed update restores both the prior consumer lock and prior CLI state. The state file is
under `${XDG_STATE_HOME:-$HOME/.local/state}/maison/cli` unless `MAISON_CLI_STATE_FILE` is set; it is local runtime
state and is not committed to either repository.
