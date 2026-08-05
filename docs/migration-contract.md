# Repository migration contract

Maison and Terroir are separate repositories with separate ownership:

| Repository                          | Role                        | Owns                                                                                                                  |
|-------------------------------------|-----------------------------|-----------------------------------------------------------------------------------------------------------------------|
| `RobertDeRose/maison`               | Public framework            | Reusable Nix modules, mise orchestration, CLI, schemas, validation, tests, and neutral documentation                  |
| `RobertDeRose/terroir`              | Private consumer            | `flake.nix`, `flake.lock`, inventory, hosts, mise policy, dotfiles, deployment state, and personal/site configuration |
| archived private `terroir.original` | Historical consumer source  | The pre-split personal/site configuration used to seed the fresh Terroir history                                      |
| archived `nix-config`               | Historical framework source | The complete pre-split history and recovery reference                                                                 |

Terroir is a consumer repository, not a second Maison checkout or command surface. Bitwarden and the consumer-selected
fnox provider remain authoritative for passwords, tokens, private keys, and other confidential values. No secret value or
private key is copied into either repository.

## Migration order

1. Freeze the archived private Terroir source and the source framework checkout; preserve both complete Git histories.
2. Produce a reviewable manifest classifying every candidate path as public Maison content, private Terroir content,
   neutral replacement, or excluded material. Record the destination and rationale.
3. Obtain explicit approval of the manifest before copying, replacing, or deleting any candidate path.
4. Create fresh Git repositories for Maison and Terroir. Do not reuse `.git`, refs, source commits, or source author
   metadata. Maison retains its dstack/Copier project controls; Terroir remains a plain configuration repository.
5. Populate each repository only from approved manifest entries. Replace public personal data with neutral examples and
   exclude secrets, private keys, real endpoints, and unrelated machine state.
6. Validate both repositories without system activation: public-privacy scans, raw-secret scans, inventory validation,
   consumer validation, flake checks, documentation checks, and fresh-history checks.
7. Confirm the new checkouts and their remotes before changing the source repository's visibility or archive state.
8. Make the historical `nix-config` repository private and archived only after all validation and remote checks pass.
9. Retain the approved manifest, source backup, staging trees, and migration evidence until the operator confirms the
   transition.

## Fresh-history requirements

The public Maison history must contain only fresh logical commits and no imported source objects or private paths. The
private Terroir history may contain only approved configuration and documentation, with no raw secrets or private-key
material. A failed migration leaves both new repositories and the historical source intact for explicit repair; it never
silently deletes or publishes a repository.

## Recovery

If a new repository fails validation, stop the transition and repair it from the approved manifest. If the source must be
consulted, use the archived private `terroir.original` or `nix-config` checkout, or the preserved local source backup. Do not restore personal
configuration into public Maison. Re-run privacy, fresh-history, consumer, inventory, and documentation checks before
resuming the archive transition. The new Terroir checkout must retain a fresh history; do not import commits from
`terroir.original`.

After migration, normal operations select Terroir with `MAISON_CONSUMER_ROOT` or by running from its checkout. Maison
never stores a saved alternate configuration root and never writes the consumer's files into its own checkout.
