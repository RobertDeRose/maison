# Topology refactor report

- Source bundle commit: `e57364aa73583e160f5d66af180f0763a482a607`
- Refactor branch: `dev`
- Goal: retain Nix for OS-level state, remove Home Manager, and move user state to mise.

## Structural changes

- Removed the Home Manager input, modules, outputs, activation, and generation handling.
- Removed the generated `packages.toml` ownership layer and reduced nix-homebrew to the OS-integrated FUSE-T exception.
- Added deploy-rs nodes, a nixpkgs-aligned activation adapter, deployment checks, and system profile deployment.
- Adopted `nh darwin` for local Darwin build and switch.
- Kept system-manager for privileged Linux state.
- Converted native application configuration and package inventories to mise.
- Preserved biometric sudo, login-window policy, Caps Lock remapping, host identity, and services in Nix.
- Split aggregate workflows into explicit `system:*` and `user:*` tasks.

## Validation available in the branch

- TOML, JSON, shell, and Python syntax checks.
- Standard-library regression tests for topology and deterministic config editing.
- Inventory validation.
- Warning-free explicit evaluation of every supported flake output, realization of current-system checks, and formatting.
- Per-platform CI builds for package, check, and host outputs.

## Runtime verification still required

Before activation on a real host, run:

```bash
maison check
maison system plan
maison user plan
```

Then perform the staged deploy-rs rollback tests in `migration-contract.md` before deleting the old deployment implementation's recovery data.
