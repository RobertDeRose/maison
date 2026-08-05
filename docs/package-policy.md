# Package policy

## Decision order

1. **mise tool backend** for versioned, user-scoped developer tools with prebuilt releases.
2. **mise built-in Homebrew formula** for ordinary native CLI packages and shared-library applications.
3. **Homebrew cask or MAS through mise** for ordinary user-facing macOS applications.
4. **Nix/nix-darwin** for system-wide fonts, filesystem integrations, system services, privileged activation, and Nix
   administration workflows.

A package has one owner and may not be duplicated between `[tools]`, `[bootstrap.packages]`, and the Nix system closure.

## Consumer package files

Maison keeps neutral, schema-valid package stubs. The consumer repository owns package policy:

- `config/mise/config.toml`: cross-platform policy;
- `config/mise/config.macos.toml`: macOS policy;
- `config/mise/config.macos-arm64.toml`: Apple Silicon policy; and
- `config/mise/config.linux.toml`: Linux policy.

Common declarations remain in `config/mise/config.toml`; `package --macos` selects the Apple Silicon file. Inventory
profiles (`base`, `dev`, `mac`, and `linux`) select Nix modules, not a mise profile selector.

Intel macOS is unsupported; there is no placeholder configuration pretending to provide package parity.

## Contributor tools

Repository validation, formatting, hooks, and documentation tools live in Maison's `mise.toml`. Install them explicitly:

```bash
mise install
```

Normal `maison user apply` converges the consumer's user config and does not install Maison's contributor toolchain on
every managed host.

## Mutations

```bash
maison tool add <backend:tool> [version]
maison tool remove <backend:tool[@version]>
maison package add <manager:package> [--macos]
maison package remove <manager:package> [--macos]
maison app add <cask>
maison app remove <cask>
```

Covered operations require a clean consumer Git checkout. They preserve unrelated work, leave ignored files untouched,
refuse dirty declaration or lock targets, and create focused commits after the transaction journal completes. Commit
failures leave validated files in place for manual recovery. Removing one version of a multi-version tool runs a targeted
`mise lock --global <tool>` against candidate files; full tool removal deletes that tool's generated lock block directly.
