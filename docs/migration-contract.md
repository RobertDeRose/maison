# Migration contract

Baseline bundle commit: `49e34f89715a5500e4aa15042dd65cc4483586e8`.

This document records where behavior moved before Home Manager and bespoke deployment logic were removed.

## Final repository boundary

The MAISON-017 transition completed after the public/private validation gate:

- `https://github.com/RobertDeRose/maison` is the public framework and defaults to `main`.
- `https://github.com/RobertDeRose/terroir` is the private overlay and defaults to `main`.
- `https://github.com/RobertDeRose/nix-config` is the private archived historical source; its local checkout and
  history remain preserved for recovery.

The approved owner-only migration manifest and Bitwarden remain the recovery sources for excluded private material.

| Previous behavior                                      | New owner / implementation                                                                                 | Validation                                                                            |
|--------------------------------------------------------|------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| Darwin build and switch                                | `nh darwin` through `system:plan` / `system:apply`                                                         | Build and switch the inventory host                                                   |
| Linux system build                                     | `systemConfigs.<host>`                                                                                     | `system:plan --host <host>`                                                           |
| Linux closure copy and activation                      | deploy-rs `profiles.system`                                                                                | Deploy checks plus staged remote test                                                 |
| Linux generation profile                               | `/nix/var/nix/profiles/system-manager-profiles/system-manager`                                             | `system:history`                                                                      |
| Darwin biometric sudo                                  | nix-darwin PAM module                                                                                      | Fresh sudo credential prompts with Watch/Touch ID                                     |
| Login-window guest policy                              | nix-darwin                                                                                                 | Inspect resulting login-window preference                                             |
| Caps Lock to Escape                                    | nix-darwin keyboard module                                                                                 | Verify after system activation                                                        |
| Nix daemon/cache policy                                | Darwin/common Nix modules and Linux system-manager                                                         | `nix show-config`                                                                     |
| Git configuration                                      | mise dotfiles under `~/.config/git`                                                                        | `git config --list --show-origin`                                                     |
| Existing `~/.gitconfig` conflict                       | `scripts/user-prepare.sh` backup                                                                           | Backup under `~/.local/state/maison/backups/git`                                      |
| Existing whole-file dotfile conflicts                  | Forced `user:apply` detects mise refusals, copies their contents, then replaces them                       | Timestamped backup under `~/.local/state/maison/backups/dotfiles`                     |
| Live application bundles retained under Maison backups | `scripts/user-prepare.sh` archives them with `ditto`, unregisters the bundle, and prevents backup indexing | No `.app` directory remains under the backup root; a non-empty `.app.zip` is retained |
| Zsh, Starship, fzf, direnv, eza, Yazi integration      | Native dotfiles plus mise/Homebrew packages                                                                | New login shell and completion checks                                                 |
| Helix, Ghostty, Zed, htop                              | Native dotfiles                                                                                            | Start each application and inspect config path                                        |
| Pi extensions and mutable settings                     | mise dotfiles plus merge in `user-finalize.sh`                                                             | Existing package selections remain present                                            |
| SSH client / Bitwarden agent                           | Tera SSH config and macOS environment                                                                      | `ssh -G <host>` and agent socket check                                                |
| Finder workflows                                       | mise copy-mode dotfiles                                                                                    | Services visible after login/Finder refresh                                           |
| CLI packages formerly in nixpkgs/Home Manager          | mise tools or built-in Homebrew packages                                                                   | `mise bootstrap status`                                                               |
| User-facing formulae, casks, and MAS apps              | mise `config.macos-arm64.toml`                                                                             | Package status and application launch                                                 |
| System-wide fonts                                      | nix-darwin `fonts.nix`                                                                                     | Font visible to login/session applications                                            |
| FUSE-T filesystem integration                          | nix-darwin plus minimal nix-homebrew module                                                                | Mount and SSHFS integration test                                                      |
| Home Manager generations                               | Removed                                                                                                    | No `homeConfigurations` or Home Manager input                                         |
| Linux user activation after deploy                     | remote `mise run user:apply`; system closure retains curl/Git/tar prerequisites                            | Separate user convergence result                                                      |
| Remote repository replacement                          | committed-only revision archive with root-owned same-filesystem transaction state                          | Failed user convergence restores the prior repository                                 |
| Linux "rollback" by deactivation                       | Real profile rollback plus activation                                                                      | Generation A/B rollback test                                                          |

## Required staged verification

Before treating deploy-rs as the only deployment path:

1. Deploy Linux system generation A.
2. Deploy generation B and verify both appear in history.
3. Intentionally fail activation of C and confirm B is reactivated.
4. Intentionally disrupt SSH during D and confirm magic rollback restores connectivity.
5. Roll back manually from B to A.
6. Run `system:clean` and confirm active/retained profiles remain valid.
7. Apply the user layer separately and verify a user-layer failure does not alter the active system profile.

## Removable backups

Do not delete these until the new topology has been used successfully:

- `/etc/nix/nix.conf.before-nix-darwin`
- `/etc/nix/nix.custom.conf.before-nix-darwin`
- Incomplete root-owned Maison transaction rollback trees under `/home/.maison-deploy/transactions/`
- `~/.local/state/maison/backups/git/*`
- `~/.local/state/maison/backups/dotfiles/*`
- `~/.local/state/maison/backups/pi/*`
- Archived `~/.local/state/maison/backups/**/*.app.zip` bundles
- Old Nix system generations
