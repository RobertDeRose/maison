
# Maison overview

- Project kind: `infrastructure`
- Public repository: `RobertDeRose/maison`
- Private overlay: `RobertDeRose/terroir`

## Purpose

Maison is a two-layer macOS and Linux configuration system that uses Nix/Lix for privileged system state and mise for user tools, packages, applications, preferences, and dotfiles.

## Intended users

The primary users are the repository maintainer and future contributors/operators who need to bootstrap, validate, apply, recover, and remotely deploy supported Maison-managed hosts.

## Current scope

Maison manages Apple Silicon macOS, aarch64 Linux, and x86&#95;64 Linux host configuration; local system activation; remote Linux deployment; user-environment convergence; inventory validation; package/tool/app authoring commands; recovery; and project documentation.

Future behavior belongs in [Planned features](../planned-features.md) until delivered.

## Repository boundaries

Public Maison owns reusable framework code, neutral examples, tests, documentation, dstack/Copier controls, and
validation tooling. Private Terroir owns real inventory, hosts, site package policy, personal dotfiles, and non-secret
trusted configuration. The former `RobertDeRose/nix-config` repository is retained as a private archived migration source.
Bitwarden owns passwords, tokens, secret values, SSH private keys, signing private keys, and other private key material.

## Boundaries

Maison does not support Intel macOS, Home Manager, arbitrary unmanaged package ownership, strict offline byte-for-byte reproduction, or storing private infrastructure identity and trusted access material in the public control plane.
