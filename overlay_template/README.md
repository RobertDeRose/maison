# Maison consumer

This repository was generated from Maison's Copier starter. It owns the inventory, host topology, user mise policy,
dotfiles, deployment state, and the consumer flake/lock. Maison remains the reusable framework.

## Finish setup

Bootstrap creates the initial host entry, pins `flake.lock`, and stops for review without activation. Inspect the
inventory and flake, create the first consumer commit, then rerun `bootstrap.sh --consumer` to activate it. For a manual
Copier render, use the same review and commit sequence before ordinary authoring:

```bash
nix flake lock "path:$PWD"
nix flake check --no-update-lock-file
MAISON_CONSUMER_ROOT="$PWD" maison consumer validate
MAISON_CONSUMER_ROOT="$PWD" git add -A && git commit -m "chore: initialize consumer"
MAISON_CONSUMER_ROOT="$PWD" maison plan
```

The template can be updated with `copier update --trust`; review generated changes before applying them. Host changes
belong in the consumer and should use `maison host add`, which validates and transactionally edits `inventory.toml`.

Keep passwords, tokens, SSH private keys, signing private keys, and other secrets in Bitwarden or the consumer-selected
fnox provider. A private Git repository is not a substitute for secret storage.
