# Maison overview

- Project kind: `infrastructure`
- Public framework: `RobertDeRose/maison`
- Consumer repository: an installation-specific Git repository

## Purpose

Maison is a reusable macOS and Linux configuration framework. Nix/Lix owns privileged system state; mise owns consumer
user tools, packages, applications, preferences, and dotfiles.

## Intended users

The primary users are maintainers and operators who bootstrap, validate, apply, recover, and remotely deploy supported
Maison-managed hosts.

## Current scope

Maison manages Apple Silicon macOS, aarch64 Linux, and x86_64 Linux host configuration; local system activation; remote
Linux deployment; consumer user-environment convergence; inventory validation; package/tool/app authoring; recovery; and
documentation.

## Repository boundaries

Maison owns reusable framework code, neutral examples, tests, documentation, dstack controls, and validation tooling. The
consumer owns `flake.nix`, `flake.lock`, `inventory.toml`, host topology, mise policy, dotfiles, deployment state, and
personal configuration. Bitwarden owns passwords, tokens, secret values, SSH private keys, signing private keys, and other
private key material.

## Boundaries

Maison does not support Intel macOS, Home Manager, arbitrary unmanaged package ownership, strict offline byte-for-byte
reproduction, or storing private infrastructure identity and trusted access material in the public framework.
