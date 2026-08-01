# Inventory reference

Maison inventory is TOML with `schema = 1`. The public schema contract lives at `schemas/inventory.toml`; Python and
Nix validators load that same file for supported systems, profile names, feature keys, deploy keys, and defaults.

Public Maison ships only a neutral starter inventory. Real users, host names, deployment endpoints, and host overrides
belong in the private Terroir overlay under the mirrored `inventory.toml` and `hosts/` paths. Inventory may contain
non-secret topology, but passwords, tokens, SSH private keys, signing private keys, and other secrets remain in Bitwarden.

## Top-level tables

| Field             | Required | Contract                                                                                 |
|-------------------|----------|------------------------------------------------------------------------------------------|
| `schema`          | Yes      | Must equal `1`.                                                                          |
| `[defaults] user` | Optional | Default inventory user key for hosts that omit `user`.                                   |
| `[users.<key>]`   | Yes      | Declares managed user identities.                                                        |
| `[hosts.<name>]`  | Yes      | Declares host system, user, profiles, optional features, and optional deployment fields. |

## Users

| Field               | Default  | Contract                                                                  |
|---------------------|----------|---------------------------------------------------------------------------|
| `username`          | User key | Portable lowercase account name. `root` is not allowed as a managed user. |
| `full_name`         | None     | Required non-empty display name.                                          |
| `email`             | None     | Required non-empty email string.                                          |
| `github`            | None     | Required GitHub username.                                                 |
| `allow_nonportable` | `false`  | Allows an existing non-portable username only on Darwin hosts.            |

## Hosts

| Field           | Contract                                                                        |
|-----------------|---------------------------------------------------------------------------------|
| Host table name | One DNS label.                                                                  |
| `system`        | One of `aarch64-darwin`, `aarch64-linux`, or `x86_64-linux`.                    |
| `user`          | Existing user key, or `[defaults].user`.                                        |
| `profiles`      | Non-empty list from `base`, `dev`, `mac`, and `linux`; duplicates are rejected. |

The `mac` profile is Darwin-only. The `linux` profile is Linux-only.

## Features

`[hosts.<name>.features]` accepts only keys declared by `schemas/inventory.toml`.

| Field            | Default | Contract |
|------------------|---------|----------|
| `personal_cache` | `false` | Boolean. |

## Deployment

`[hosts.<name>.deploy]` accepts only keys declared by `schemas/inventory.toml`.

| Field            | Default                        | Contract                                                                             |
|------------------|--------------------------------|--------------------------------------------------------------------------------------|
| `enable`         | `false`                        | Boolean; deploy-rs is Linux-only when enabled.                                       |
| `hostname`       | Host table name                | Remote host name.                                                                    |
| `ssh_user`       | `maison-deploy`                | Deployment account; may be `root` for bootstrap but must not equal the managed user. |
| `user_ssh_user`  | Managed username               | Must equal the managed inventory username.                                           |
| `repo_path`      | `/home/<managed-user>/.maison` | Normalized descendant of `/home/<managed-user>`, not the home directory itself.      |
| `remote_build`   | `false`                        | Boolean deploy-rs option.                                                            |
| `auto_rollback`  | `true`                         | Boolean deploy-rs rollback option.                                                   |
| `magic_rollback` | `true`                         | Boolean deploy-rs rollback option.                                                   |

## Overlay inventory and host overrides

When a Terroir overlay clone contains `inventory.toml`, Maison validates that active inventory and its sibling `hosts/`
tree. Host override directories must correspond to inventory hosts and may contain only `system.nix`. User-level
differences belong in Terroir mise configuration or dotfiles, not host override modules. Overlay inventory replaces the
public starter inventory; it is not merged with it.

## Fixture contract

Inventory fixtures live under `tests/fixtures/inventory/`. Valid and invalid cases are consumed by both Python and Nix
validation so CI fails when their accepted fields, defaults, type checks, profiles, feature keys, deploy keys, or deploy
path rules drift.
