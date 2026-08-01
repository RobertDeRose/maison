# Design — MAISON-017: Maison/Terroir repository split

## Metadata

- Beads feature root: `maison-mol-jfhs`
- Feature slug: `maison-017-maison-terroir-repository-split`
- Design path: `docs/src/features/maison-017-maison-terroir-repository-split/design.md`
- Implemented record: `docs/src/features/maison-017-maison-terroir-repository-split/index.md`
- Base branch: `dev`
- Status: draft

## Feature Summary

Create the two repositories that the Maison architecture describes but the existing `nix-config` repository does not
yet provide: a new public `RobertDeRose/maison` framework repository and a new private `RobertDeRose/terroir`
configuration repository. Preserve the existing `nix-config` checkout and history as a private archived migration source.

## User Intent

The user wants Maison to be the reusable public vehicle and Terroir to be the private driver containing actual personal and
site configuration. The new repositories must start with fresh logical commits rather than importing the existing public
history. The public repository should use the dstack workflow and may be initialized through `/setup-project`; Terroir is a
plain private data/configuration repository. Bitwarden remains the source of truth for secrets and private keys.

The migration source is the current `nix-config` checkout and its Git history. Migration first generates a candidate
manifest and requires explicit user approval before moving, replacing, or deleting any candidate path.

## Goals

- Create a clean public `RobertDeRose/maison` repository containing reusable framework code, neutral examples, tests,
  documentation, and dstack project controls.
- Create a private `RobertDeRose/terroir` repository containing the approved personal/site configuration in the mirrored
  overlay layout expected by Maison.
- Give each new repository a fresh, reviewable logical commit history with no imported `nix-config` commits or metadata.
- Preserve the complete original `nix-config` history by making `RobertDeRose/nix-config` private and archiving it only
  after both new repositories pass validation.
- Create separate local checkouts at `../maison` and `../terroir`, and configure Maison to use Terroir as its overlay.
- Make the final split reproducible and auditable through an approved candidate manifest, validation evidence, and
  documented transition steps.

## Non-Goals

- Storing passwords, tokens, secret values, SSH private keys, signing private keys, or other private key material in
  Terroir; Bitwarden remains the secret store.
- Rewriting or force-pushing the existing `nix-config` history; that repository becomes the private archive.
- Carrying any old commit history, author metadata, Git refs, or Beads interaction history into either new repository.
- Applying a system configuration or changing machine state as part of the repository migration.
- Adding the dstack workflow, Beads, or Copier controls to Terroir.
- Automatically moving files without an approved candidate manifest.
- Deleting the source checkout or deleting either newly created remote repository on a failed migration.

## User-Facing Behavior

After delivery, the public workflow is:

```bash
git clone https://github.com/RobertDeRose/maison.git
cd maison
./bootstrap.sh --host "$(hostname -s)" --overlay git@github.com:RobertDeRose/terroir.git
```

Maison stores the selected overlay source using its existing XDG overlay-state contract. The Terroir checkout mirrors
supported owned paths such as `inventory.toml`, `hosts/`, `config/mise/*.toml`, `dotfiles/`, and non-secret trusted
configuration. Users retrieve secrets and private keys from Bitwarden rather than from either repository.

The old `nix-config` GitHub repository remains available as a private archived record and is not an active public source.

## Requirements

### Functional Requirements

- Inspect the current `nix-config` working tree and Git history, classify candidate personal/site paths, and emit a
  reviewable manifest containing each source path, destination repository/path, action, and rationale.
- Require explicit approval of the candidate manifest before any source path is removed, replaced, or copied as private
  data.
- Create `RobertDeRose/maison` as a new public repository from a fresh dstack/Copier scaffold using `/setup-project` or
  its equivalent setup helper. Use the stable dstack template, `main` as the default branch, and the project brief fixed
  by this design.
- Create `RobertDeRose/terroir` as a new private plain Git repository with `main` as the default branch and the
  documented overlay layout.
- Refuse to overwrite an existing repository with either target name; report the conflict for explicit operator handling.
- Populate both repositories from fresh staging checkouts, preserving only approved content and generated dstack controls.
- Commit each new repository in several logical commits without importing source history, source refs, or source commit
  metadata.
- Verify that the public Maison tree and all reachable public Git objects contain no approved private paths, personal
  identity, real infrastructure metadata, or secret material.
- Verify that Terroir contains the approved private configuration but no raw secrets or private keys.
- Verify Maison can load and validate Terroir as an overlay without system activation.
- After validation, make `RobertDeRose/nix-config` private and archive it. Do not archive it before validation succeeds.
- Leave local source and migration backups intact until the remote transition is confirmed.

### Quality Requirements

- Preserve the existing Nix/Lix system versus mise user ownership boundary and supported platform set.
- Keep the public Maison repository reproducible through Copier metadata, dstack lifecycle controls, committed lockfiles,
  documentation validation, and repository checks.
- Keep migration actions ordered and failure-safe: manifest approval, staging, validation, publication, then old-repository
  archival.
- Make privacy checks deterministic and auditable; a failed privacy or remote-state check blocks archival.
- Do not expose remote credentials, Bitwarden values, or private repository contents in logs or committed artifacts.

### Compatibility and Migration Requirements

- Preserve Maison's existing command names, overlay source precedence, inventory schema, mirrored overlay paths, supported
  platforms, and deployment boundaries.
- Preserve public starter behavior when no overlay is selected, subject to the existing documented overlay-required mode.
- Use `RobertDeRose/maison` and `RobertDeRose/terroir` as the canonical repository identities.
- Keep `nix-config` private and archived as the historical source of truth after the split; do not treat it as a supported
  public clone target.
- Keep Terroir independent of dstack while documenting its expected Maison overlay layout and secret boundary.

## Existing Context

MAISON-004 implemented the public-side overlay contract: `--overlay`, local XDG source state, cloning/updating, typed
inventory loading, and mirrored overlay paths. It did not create or populate a private overlay repository. The current
repository is still named `nix-config`, has only its existing public remote, and has no active overlay checkout or saved
overlay source.

The current repository already contains the Maison framework, dstack/Copier project controls, Nix/Lix and mise ownership
boundaries, supported platform contracts, overlay loader, validators, tests, and reader documentation. The current public
history must not be reused for the new public repository because the desired public result is a clean fresh repository.
The Beads implementation remains controlled from the current `nix-config` repository and its feature worktree; the new
Maison and Terroir repositories are migration outputs, not alternate Beads control planes for this feature.

## Proposed Design

### Migration phases

1. **Freeze and audit**
   - Treat the current `nix-config` checkout as the immutable migration source.
   - Scan current files and history for personal/site configuration and private data candidates.
   - Produce a manifest with `source`, `destination_repo`, `destination_path`, `action` (`public`, `private`, `replace`,
     or `exclude`), and rationale.
   - Present the manifest for explicit approval. No destructive or private-copy action occurs before approval.

2. **Create fresh repository shells**
   - Create empty local destinations `<maison-checkout>` and `<terroir-checkout>` without
     reusing the source `.git` directory.
   - Run the stable `/setup-project maison` workflow in the empty Maison destination with these fixed answers:
     - purpose: reusable public configuration framework for supported macOS and Linux systems;
     - users: Maison maintainers and operators managing supported personal or site hosts;
     - scope: Nix/Lix system state, mise user state, inventory, local/remote deployment, convergence, recovery, and
       validation for Apple Silicon macOS and supported Linux;
     - boundaries: personal identity, real infrastructure metadata, trusted private material, secrets, and host-specific
       configuration belong in Terroir or Bitwarden; Intel macOS and Home Manager remain unsupported;
     - project kind: `infrastructure`;
     - language profiles: `nix`, `python`, and `typescript`;
     - repository layout: `single-package`.
   - Treat the generated setup-project scaffold as authoritative for `.copier-answers.yml`, `AGENTS.md`, `.beads/`,
     `docs/book.toml`, feature templates, `scripts/setup-tooling.py`, `mise.toml`, hooks, and other project-control files.
     Source framework files may populate the scaffold only where the manifest assigns ownership; collisions with generated
     controls stop for review rather than silently overwriting the new project baseline.
   - Initialize Terroir as a plain Git repository with only a small README, ignore policy, and supported overlay layout.
   - Create the GitHub repositories under the authenticated `RobertDeRose` account with public/private visibility as
     specified, refusing conflicts.

3. **Populate and commit**
   - Copy reusable framework files into Maison while preserving the newly generated dstack/Copier controls and excluding
     old `.git`, `.beads` runtime/history, private candidates, and migration-only source artifacts.
   - Copy only manifest-approved private paths into Terroir using the existing overlay layout. Replace public paths with
     neutral starter files where the approved manifest requires a public example; exclude paths with no safe public form.
   - Use several fresh logical commits in each repository. The exact commit boundaries are implementation detail, but the
     histories must not contain source commits or source author metadata.
   - Set Maison's overlay source to `git@github.com:RobertDeRose/terroir.git` in the local migration checkout only after
     the private remote is available; do not commit machine-local overlay state.

4. **Validate and transition**
   - Run dstack setup verification, Maison documentation checks, shell/data/Nix/Python/TypeScript checks, privacy scans,
     overlay fixture checks, and non-activating Maison/Terroir inventory validation.
   - Verify remote repository visibility, default branches, commit ancestry, and fresh-history boundaries through GitHub
     and local Git inspection.
   - Verify the new local checkouts and overlay state without performing system activation.
   - Only after every required check passes, set `RobertDeRose/nix-config` private and archived, then record the archive
     state and final repository URLs in the migration record.

5. **Document and preserve**
   - Update public Maison documentation to describe the two-repository model, the Terroir overlay, Bitwarden boundary,
     source/archive transition, and recovery path.
   - Retain the original private archived repository and local source backup until the user confirms the transition.

### Repository boundaries

```text
public RobertDeRose/maison
├── reusable Maison code, tests, Nix modules, mise task machinery
├── neutral inventory/examples and public documentation
├── dstack/Copier project controls and validation tooling
└── no personal/site identity or secret material

private RobertDeRose/terroir
├── inventory.toml and hosts/
├── personal/site config/mise declarations
├── personal/site dotfiles and preferences
├── non-secret trusted configuration
└── no passwords, tokens, or private keys; Bitwarden remains authoritative

private archived RobertDeRose/nix-config
└── complete historical migration source and rollback reference
```

## Architecture Consistency

### Existing Patterns Reused

- MAISON-004 overlay discovery, state precedence, typed inventory validation, and mirrored data paths.
- The existing Nix/Lix system and mise user ownership boundary.
- dstack/Copier setup and feature lifecycle for the public Maison repository.
- Existing repository mutation, backup, validation, and authoring-checkout safety contracts.

### Invariants Preserved

- Public Maison contains no personal infrastructure identity or trusted private material.
- A configuration path has one owning repository after migration: reusable framework in Maison or personal/site data in
  Terroir.
- Secrets and private keys are not stored in either repository.
- Old source history remains recoverable in the private archived `nix-config` repository.
- No remote archive or source cleanup happens before new-repository validation succeeds.

### New Decisions Introduced

- The canonical public repository is `RobertDeRose/maison`.
- The canonical private overlay repository is `RobertDeRose/terroir`.
- `nix-config` is a private historical archive, not a future public repository.
- New repositories start with fresh logical commits and no imported source history.
- Only Maison uses dstack; Terroir remains a plain data/configuration repository.
- Bitwarden owns secrets and private keys.
- Migration uses an explicit approved candidate manifest.

### Architecture Documentation Changes

Update the public Maison architecture page to describe the repository pair, source-of-truth ownership, and archived
migration source. Keep the overlay state path local and untracked, and document that Terroir is data/configuration rather
than a second framework or command surface.

## Operational Considerations

- Operators clone Maison and provide Terroir with `--overlay` or the existing overlay source mechanisms.
- Terroir changes are ordinary Git authoring changes; Maison validates the active overlay before planning or deployment.
- Bitwarden remains required for any secret or private-key material; migration must report excluded secret candidates
  without copying their values.
- If repository creation, manifest approval, validation, or remote transition fails, leave all source and staging trees
  intact and do not archive `nix-config`.
- If the new remotes are created but later validation fails, mark the transition incomplete and preserve the repositories
  for explicit repair rather than deleting them automatically.
- Recovery uses the private archived `nix-config`, local staging copies, and the approved manifest; it does not rely on
  public history.

## Documentation Impact

| Documentation concern | Exact page                                                              | Create or update        | Planned change                                                                         | Owning Beads task                        |
|-----------------------|-------------------------------------------------------------------------|-------------------------|----------------------------------------------------------------------------------------|------------------------------------------|
| Introduction          | `README.md`                                                             | Update                  | Explain Maison/Terroir repository roles and first clone/bootstrap flow                 | `maison-mol-ieqc.4`                      |
| Introduction          | `docs/src/introduction/project-overview.md`                             | Update                  | State the public framework/private overlay split and Bitwarden boundary                | `maison-mol-ieqc.4`                      |
| Architecture          | `docs/architecture.md`                                                  | Update                  | Define public Maison, private Terroir, Bitwarden, and archived nix-config ownership    | `maison-mol-ieqc.4`                      |
| Usage / Operations    | `docs/operations.md`                                                    | Update                  | Document fresh setup, local checkouts, overlay selection, and transition recovery      | `maison-mol-ieqc.4`                      |
| Recovery              | `docs/recovery.md`                                                      | Update                  | Document archived-source recovery and failed split/remote-transition handling          | `maison-mol-ieqc.4`                      |
| Deployment            | `docs/deployment.md`                                                    | Update                  | Align deployment source and overlay repository guidance with the new canonical remotes | `maison-mol-ieqc.4`                      |
| Migration contract    | `docs/migration-contract.md`                                            | Update                  | Record the two-repository migration boundary and archive sequencing                    | `maison-mol-ieqc.4`                      |
| Inventory reference   | `docs/src/reference/inventory.md`                                       | Update                  | Clarify Terroir mirrored layout and secret exclusions                                  | `maison-mol-ieqc.4`                      |
| Development           | `docs/src/development/tooling.md`                                       | Update                  | Document dstack-managed Maison setup and fresh-repository validation commands          | `maison-mol-ieqc.4`                      |
| Navigation            | `docs/src/SUMMARY.md`                                                   | Update if needed        | Register the design and implemented record; register any new durable page              | `maison-mol-ako9`, `maison-mol-ryxl`     |
| Roadmap               | `docs/src/planned-features.md`                                          | Update                  | Add MAISON-017 with migration sequencing and dependency                                | `maison-mol-ako9`                        |
| Feature index         | `docs/src/features/index.md`                                            | Update during close-out | Add the delivered migration record                                                     | `maison-mol-ryxl`                        |
| Implemented record    | `docs/src/features/maison-017-maison-terroir-repository-split/index.md` | Create during close-out | Preserve migration, remote, validation, and archive evidence                           | `maison-mol-ryxl`                        |
| Terroir README        | `README.md` in `RobertDeRose/terroir`                                   | Create                  | State overlay layout, no-secret policy, and Maison relationship                        | `maison-mol-ieqc.3`, `maison-mol-ieqc.4` |

## Validation Strategy

- Candidate manifest audit over current files and Git history, including path classification and private-data scan.
- Explicit user approval recorded before migration actions.
- `/setup-project` verification for Maison: Copier provenance, dstack files, `main` branch, generated docs, Beads, locked
  tooling, and no legacy migration utilities.
- Fresh-history checks for both repositories: no source `.git` reuse, no imported source commits, and only fresh logical
  commits.
- Public privacy checks over Maison working tree and reachable Git objects for private paths, identities, real endpoints,
  secret patterns, and private-key markers.
- Terroir content checks against the approved manifest and scans rejecting raw secrets/private keys.
- `uv run scripts/check-docs.py` and `mise -E dev run check` in the new Maison repository.
- Existing overlay/inventory contract tests against a local Terroir fixture or checkout without system activation.
- `git diff --check`, `shellcheck`, and relevant dstack/mise/hk checks.
- GitHub remote checks for `RobertDeRose/maison` public, `RobertDeRose/terroir` private, both defaulting to `main`, and
  `RobertDeRose/nix-config` private plus archived only after successful validation.
- Final local checkout and saved-overlay-state verification; no system activation is required or permitted by this feature.

## Implementation Decomposition

- **Candidate manifest and privacy audit** (`maison-mol-ieqc.1`) — inspect current tree/history, classify paths, produce
  the approved migration manifest, and record excluded secret/private-key candidates.
- **Maison public scaffold** (`maison-mol-ieqc.2`) — create the new public repository with `/setup-project`, dstack
  controls, stable tooling, and fresh local/remote repository state.
- **Terroir private scaffold** (`maison-mol-ieqc.3`) — create the private plain repository, overlay directory layout,
  README, ignore policy, and fresh local/remote repository state.
- **Content split and fresh commits** (`maison-mol-ieqc.4`) — populate both repositories from the approved manifest,
  configure local checkouts, and create fresh logical histories.
- **Validation and archive transition** (`maison-mol-ieqc.5`, `maison-mol-ieqc.6`) — run all privacy/overlay/dstack/remote
  checks, then make old `nix-config` private and archived and record final evidence.

## Dependencies and Parallelism

- This feature follows MAISON-016 and depends on its delivered public framework state.
- All implementation children depend on specification reconciliation.
- `maison-mol-ieqc.2` and `maison-mol-ieqc.3` may proceed in parallel after specification reconciliation, but neither may
  populate data before the candidate manifest is approved.
- `maison-mol-ieqc.4` depends on the approved manifest and both scaffolds.
- `maison-mol-ieqc.5` depends on the completed content split and fresh-history checks.
- `maison-mol-ieqc.6` depends on successful validation and is the only task allowed to archive `nix-config`.
- Documentation reconciliation and final validation occur after the new public repository's reader-facing pages are
  available.

## Rollout and Migration

1. Freeze the source checkout and create the candidate manifest.
2. Obtain explicit approval of the manifest.
3. Create both new repository shells and verify ownership/visibility before copying data.
4. Populate fresh local histories and push only after local validation.
5. Validate public/private boundaries, overlay loading, and dstack checks.
6. Make `nix-config` private and archive it.
7. Verify final remotes, local checkouts, overlay source, and documentation.

## Risks and Tradeoffs

- Automated classification can miss context, so the manifest approval gate is mandatory.
- New fresh histories lose useful public provenance, but eliminate legacy identity and privacy ambiguity.
- Making `nix-config` private before remote verification reduces public exposure but must not happen before the new public
  repository is independently usable; the ordered transition prevents both failure modes.
- A private Terroir repository still needs normal access control and Bitwarden discipline; GitHub privacy is not a substitute
  for secret management.
- dstack setup creates a new project control plane, so only approved reusable content and generated controls may replace
  the scaffold.

## Rejected Alternatives

- Reusing or force-rewriting the existing public `nix-config` history.
- Keeping personal configuration in the public Maison repository with only documentation-level separation.
- Calling the private repository `dotfiles` when it also owns inventory, hosts, package policy, and site configuration.
- Making Terroir a second dstack project or framework repository.
- Storing secrets or private keys in Terroir because it is private.
- Automatically deleting the source repository or failed staging repositories during migration.

## Open Questions

None required for the planned implementation tasks.

## Deferred Decisions

- Exact logical commit boundaries may be selected by the implementation coordinator while preserving fresh-history and
  audit requirements.
- The exact private overlay source syntax (`ssh`, HTTPS, or local path during testing) may follow the existing Maison
  source-precedence contract; the canonical remote is `git@github.com:RobertDeRose/terroir.git`.

## Planning Record

### Questions Asked and Answers

- Private repository name: `terroir`.
- Public repository name: `maison`.
- Public owner and private owner: `RobertDeRose`.
- Source: current `nix-config` checkout and its Git history.
- Migration safety: generate a candidate manifest and require explicit approval before changes.
- New histories: fresh logical commits; do not import source history.
- Existing repository: make `RobertDeRose/nix-config` private and archive it after successful verification.
- Public workflow: initialize `maison` through `/setup-project` and use dstack.
- Private workflow: keep `terroir` as a plain private data/configuration repository.
- Secret storage: Bitwarden owns secrets and private keys; repositories contain no raw secret/private-key material.
- Local layout: preserve the source checkout and create separate `maison` and `terroir` checkouts.

### Assumptions

- The authenticated `gh` account is `RobertDeRose` and has permission to create both repositories and update/archive
  `nix-config`.
- The existing `nix-config` checkout is the authoritative migration source and implementation control plane until the
  manifest is approved; its repository-relative implementation path is `.`.
- The current MAISON-004 overlay layout and validation contracts remain the compatibility target.
- Remote repository names are available; conflicts stop the migration rather than triggering overwrite behavior.

### Design Changes During Planning

- The first idea was a single private `dotfiles` repository. It was refined into two new repositories: public `maison`
  and private `terroir`, while the existing `nix-config` becomes a private archive.
- The private repository name changed from `dotfiles` to `terroir`.
- The split changed from history cleanup of the existing public repository to fresh new histories plus private archival of
  the old repository.
- The private repository was explicitly kept outside dstack and secrets were explicitly assigned to Bitwarden.

### Source Material

- `docs/src/features/maison-004-private-overlay-configuration/design.md`
- `docs/src/features/maison-004-private-overlay-configuration/index.md`
- `README.md`
- `docs/architecture.md`
- `docs/operations.md`
- `docs/recovery.md`
- `docs/migration-contract.md`
- `docs/src/reference/inventory.md`
- `docs/src/planned-features.md`
- Existing `nix-config` tree and Git history
