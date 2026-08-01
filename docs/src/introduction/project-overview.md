
# maison overview

- Project kind: `infrastructure`

## Purpose

Provide a reusable public configuration framework for supported macOS and Linux systems.

## Intended users

Maison maintainers and operators managing supported personal or site hosts.

## Current scope

Nix/Lix system state, mise user state, inventory, local and remote deployment, convergence, recovery, and validation for Apple Silicon macOS and supported Linux.

Future behavior belongs in [Planned features](../planned-features.md) until delivered.

## Boundaries

Personal identity, real infrastructure metadata, trusted private material, secrets, and host-specific configuration belong in Terroir or Bitwarden; Intel macOS and Home Manager remain unsupported.
