# Inventory reference

Maison inventory is TOML with `schema = 1`. The public schema contract lives at `schemas/inventory.toml`; Python and
Nix validators load that same file for supported systems, profile names, feature keys, deploy keys, and defaults.

Maison ships only a neutral starter inventory. Real users, host names, deployment endpoints, and host overrides belong
in the consumer repository's `inventory.toml` and `hosts/` tree. Inventory may contain non-secret topology, but passwords,
tokens, SSH private keys, signing private keys, and other secrets remain in Bitwarden.

## Top-level tables

| Field             | Required | Contract                                                                        |
|-------------------|----------|---------------------------------------------------------------------------------|
| `schema`          | Yes      | Must equal `1`.                                                                 |
| `[defaults] user` | Optional | Default inventory user key for hosts that omit `user`.                          |
| `[users.<key>]`   | Yes      | Declares managed user identities.                                               |
| `[hosts.<name>]`  | Yes      | Declares host system, user, profiles, optional features, and deployment fields. |

## Users

| Field               | Default  | Contract                                                                  |
|---------------------|----------|---------------------------------------------------------------------------|
| `username`          | User key | Portable lowercase account name; `root` is not allowed as a managed user. |
| `full_name`         | None     | Required non-empty display name.                                          |
| `email`             | None     | Required non-empty email string.                                          |
| `github`            | None     | Required GitHub username.                                                 |
| `allow_nonportable` | `false`  | Allows an existing non-portable username only on Darwin hosts.            |

## Hosts

| Field           | Contract                                                                        |
|-----------------|---------------------------------------------------------------------------------|
| Host table name | One DNS label.                                                                  |
| `system`        | `aarch64-darwin`, `aarch64-linux`, or `x86_64-linux`.                           |
| `user`          | Existing user key, or `[defaults].user`.                                        |
| `profiles`      | Non-empty list from `base`, `dev`, `mac`, and `linux`; duplicates are rejected. |

The `mac` profile is Darwin-only. The `linux` profile is Linux-only.

## Deployment

`[hosts.<name>.deploy]` accepts only keys declared by the schema.

| Field            | Default                        | Contract                                                                        |
|------------------|--------------------------------|---------------------------------------------------------------------------------|
| `enable`         | `false`                        | Boolean; deploy-rs is Linux-only when enabled.                                  |
| `hostname`       | Host table name                | Remote host name.                                                               |
| `ssh_user`       | `maison-deploy`                | Deployment account; may be `root` for bootstrap but not the managed user.       |
| `user_ssh_user`  | Managed username               | Must equal the managed inventory username.                                      |
| `repo_path`      | `/home/<managed-user>/.maison` | Normalized descendant of `/home/<managed-user>`, not the home directory itself. |
| `remote_build`   | `false`                        | Boolean deploy-rs option.                                                       |
| `auto_rollback`  | `true`                         | Boolean deploy-rs rollback option.                                              |
| `magic_rollback` | `true`                         | Boolean deploy-rs rollback option.                                              |

## Consumer host overrides

Host override directories must correspond to consumer inventory hosts and may contain only `system.nix`. User-level
differences belong in consumer mise configuration or dotfiles, not host override modules. The consumer inventory replaces
Maison's neutral starter inventory; it is not merged with it.

## Fixture contract

Inventory fixtures live under `tests/fixtures/inventory/` and are consumed by both Python tests and Nix evaluation checks.
The parity tests compare normalized deployment defaults, accepted fields, types, profiles, feature keys, deploy keys, and
safe repository path rules.
