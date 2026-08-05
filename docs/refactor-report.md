# Repository-boundary refactor report

Maison now implements one public framework and consumer-root model. The public checkout supplies runtime code and
validation; the selected consumer supplies all installation-specific state.

## Delivered boundaries

- Maison's public flake exports the CLI, reusable system modules, orchestration helpers, schemas, and neutral fixtures.
- A consumer owns its flake, lock, inventory, host overrides, mise configuration, dotfiles, deployment state, and Git
  history.
- Nix/Lix owns privileged system state. mise owns consumer user state. fnox providers materialize confidential values only
  at the owner-controlled runtime boundary.
- `maison plan` and validation are read-only. Activation and authoring operate on the selected consumer only.
- `maison self update` transactionally updates only the consumer's Maison input and local owner-only CLI state.
- Remote deployment stages committed consumer content and keeps rollback state root-owned and separate from user state.

## Retired architecture

The old private-overlay runtime, saved alternate configuration root, and repository `publish`/`status`/`sync` commands are
not supported. Maison does retain `overlay_template/` as a Copier setup-time starter: `bootstrap.sh --setup PATH`
renders a fresh consumer, registers its first host, and pins its consumer lock. The template does not create saved
runtime state or a second framework authoring path. Consumer Git history remains explicitly managed by the consumer
operator.

The historical split sources remain private and archived as `terroir.original` and `nix-config`. Terroir is the fresh
consumer destination and Maison is the fresh public framework history. Migration evidence and recovery requirements are
recorded in the [migration contract](migration-contract.md).

## Validation

The repository checks cover data, shell, Python, Nix, documentation, consumer contracts, provider-neutral fnox fixtures,
transaction rollback, and the public flake. Validation does not require personal fnox credentials and does not activate a
system.
