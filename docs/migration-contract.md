# Migration contract

This document records where behavior moved before Home Manager and bespoke deployment logic were removed.

## Repository boundary

Maison is the reusable public framework. A consumer repository is the execution, configuration, and lock root for one
installation. The original source repository may be retained as a private archived historical source for recovery.

| Previous behavior                  | New owner / implementation                                                    | Validation                                              |
|------------------------------------|-------------------------------------------------------------------------------|---------------------------------------------------------|
| Darwin build and switch            | `nh darwin` through `system:plan` / `system:apply` against the consumer flake | Build and switch the inventory host                     |
| Linux system build                 | Consumer `systemConfigs.<host>`                                               | `system:plan --host <host>`                             |
| Linux closure copy and activation  | deploy-rs `profiles.system` from the consumer flake                           | Deploy checks plus staged remote test                   |
| Linux generation profile           | `/nix/var/nix/profiles/system-manager-profiles/system-manager`                | `system:history`                                        |
| User-facing tools and packages     | Consumer `config/mise/` through mise                                          | `mise bootstrap status`                                 |
| Linux user activation after deploy | Maison runtime convergence against the consumer checkout                      | Separate user convergence result                        |
| Remote repository replacement      | Committed-only consumer archive with root-owned transaction state             | Failed convergence restores the prior consumer revision |
| Home Manager generations           | Removed                                                                       | No `homeConfigurations` or Home Manager input           |

## Required staged verification

Before treating deploy-rs as the only deployment path:

1. Deploy Linux system generation A.
2. Deploy generation B and verify both appear in history.
3. Intentionally fail activation of C and confirm B is reactivated.
4. Intentionally disrupt SSH during D and confirm magic rollback restores connectivity.
5. Roll back manually from B to A.
6. Run `system:clean` and confirm active/retained profiles remain valid.
7. Apply the consumer user layer separately and verify a user-layer failure does not alter the active system profile.

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
