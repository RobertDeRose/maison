# Package policy

## Decision order

1. **mise tool backend** for versioned, user-scoped developer tools with prebuilt releases.
2. **mise built-in Homebrew formula** for ordinary native CLI packages and shared-library applications.
3. **Homebrew cask or MAS through mise** for ordinary user-facing macOS applications.
4. **Nix/nix-darwin** for system-wide fonts, filesystem integrations, system services, privileged activation, and Nix administration workflows.

A package does not belong in Nix merely because nixpkgs contains it. A binary must have one owner and may not be duplicated between `[tools]`, `[bootstrap.packages]`, and the Nix system closure.

## Current Nix packages

Darwin's system closure contains `nh`, `deploy-rs`, `nixd`, system-wide fonts, and FUSE-T through the minimal Nix-managed native Homebrew exception. Linux system-manager contains `nh`, the minimal curl/Git/tar bootstrap prerequisites, and packages required by system services.

## User package files

Public Maison keeps empty, schema-valid package stubs and installs no user applications by default. Personal,
organization, or site package policy belongs in a private overlay based on `examples/terroir/config/mise/`.

- `config/mise/config.toml`: neutral cross-platform policy stub.
- `config/mise/config.macos.toml`: neutral macOS policy stub.
- `config/mise/config.macos-arm64.toml`: neutral Apple Silicon policy stub.
- `config/mise/config.linux.toml`: neutral Linux policy stub.

Copy the examples into a private overlay before adding tools, formulae, casks, MAS applications, or preferences.

Intel macOS is unsupported; there is no placeholder configuration pretending to provide package parity.

## Contributor tools

Repository validation, formatting, hooks, and documentation tools live in the checkout `mise.toml`. The flake formatter reads the locked `nixfmt-rs` artifact from `mise.lock`, making that lockfile the single formatter-version source for both hk and `nix fmt`. They are installed explicitly with:

```bash
mise install
```

Normal `maison user apply` runs from the global user config and does not install repository development tools on every managed host.

## Version policy

`latest` is intentional for fast-moving workstation tools and applications. Generated mise lockfiles record resolved versions where available, but strict offline resolution is not claimed. Nix system inputs remain pinned by `flake.lock` and are updated through `maison update`.

## Source-build policy

Prefer prebuilt release artifacts and Homebrew bottles for user software. Nix source builds are acceptable only for the small system closure or an explicitly justified system dependency.

## Mutations

```bash
maison tool add <backend:tool> [version]
maison tool remove <backend:tool[@version]>
maison package add <manager:package> [--macos]
maison package remove <manager:package> [--macos]
maison app add <cask>
maison app remove <cask>
```

Add operations install or resolve against candidate configuration first and atomically replace the checked-in declaration only after success. Remove operations atomically edit the declaration and deliberately leave installed data in place. Use an active private overlay when the declaration is personal or site-specific; public Maison should receive only reusable starter defaults. Removing one version of a multi-version tool runs a targeted `mise lock --global <tool>` against candidate files so retained versions and their lock entries transition together. Full tool removal deletes that tool's generated lock block directly. Package-cache pruning remains a separate, explicit operation.
