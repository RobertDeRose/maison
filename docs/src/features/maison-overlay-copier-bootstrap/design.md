# Design — Copier-backed overlay setup and bootstrap onboarding

## Metadata

- Beads feature root: `maison-mol-5s9`
- Feature slug: `maison-overlay-copier-bootstrap`
- Design path: `docs/src/features/maison-overlay-copier-bootstrap/design.md`
- Implemented record: `docs/src/features/maison-overlay-copier-bootstrap/index.md`
- Base branch: `main`
- Status: delivered

## Feature Summary

Make private-overlay creation a first-class Maison workflow. The public `overlay_template/` directory becomes a
Copier template, bootstrap accepts the canonical `MAISON_OVERLAY` environment variable or `--overlay`, and an
interactive first run can either create an overlay now or install only the Maison command and defer configuration to
the documentation.

## User Intent

The user should not have to copy a static example or manually discover how to create the private repository. Maison
should bootstrap its reusable command surface first, then either use an explicitly selected existing overlay or guide
the user through Copier-based creation. A generated overlay should be usable immediately and should register the
current macOS or Linux host through Maison's existing `host:add` task rather than duplicating inventory mutation logic.

## Goals

- Turn `overlay_template/` into a maintained Copier template for private overlays.
- Accept `--overlay SOURCE` and `MAISON_OVERLAY=SOURCE` as the supported explicit overlay inputs.
- Preserve saved overlay state for subsequent runs and retain the legacy `MAISON_OVERLAY_SOURCE` input as a compatibility
  fallback without documenting it as canonical.
- Prompt interactively when no overlay is selected and offer immediate Copier setup.
- On a negative or non-interactive onboarding response, install Maison and its CLI but skip Nix/system/user activation,
  then print the exact documentation path for completing overlay setup.
- On immediate setup, render a private Git repository, collect identity values, detect the current supported platform,
  and invoke `mise run host:add` against the generated overlay.
- Keep platform detection and inventory mutation in Maison rather than reimplementing host schema updates in the
  template.

## Non-Goals

- Creating or publishing a remote private GitHub repository automatically.
- Storing secrets, private keys, or real infrastructure values in the public template.
- Replacing Maison's existing inventory schema or `host:add` task.
- Running system activation without an explicit or newly generated overlay.
- Supporting Intel macOS or platforms outside Maison's existing supported systems.
- Making Copier a runtime dependency of every Maison user after setup; it is an ephemeral setup tool used through the
  locked Maison `uv` runtime.

## User-Facing Behavior

### Overlay selection

Bootstrap resolves sources in this order:

1. `--overlay SOURCE` for the current invocation;
2. `MAISON_OVERLAY=SOURCE`;
3. legacy `MAISON_OVERLAY_SOURCE=SOURCE` for compatibility;
4. the source saved in `${XDG_STATE_HOME:-$HOME/.local/state}/maison/overlay.toml`.

An explicit local Git repository is used directly as the active overlay path. A remote Git URL is cloned or fast-forward
updated at `${XDG_DATA_HOME:-$HOME/.local/share}/maison/overlay`, preserving the existing owner-only state file.

### First-run onboarding

When no source is available:

- An interactive terminal asks whether to set up a private overlay now, with yes as the default.
- **Yes** installs the minimal Copier runner, renders `overlay_template/` into
  `${MAISON_OVERLAY_HOME:-$HOME/src/maison-overlay}`, seeds the inventory username from `id -un`, initializes its Git
  repository, and runs the template task that registers the current host through Maison.
- **No** installs Maison's verified mise runtime and `maison` CLI, prints the overlay setup documentation URL/path, and
  exits successfully without installing Nix or applying system/user state.
- A non-interactive run behaves like No unless `MAISON_REQUIRE_OVERLAY=true`, in which case it fails with an actionable
  missing-overlay error.

After an overlay is supplied or generated, bootstrap stores it, installs missing Nix/Lix as before, and continues with
Maison's existing system and user convergence flow.

### Copier template

The template asks for the private overlay's inventory user identity and renders a valid inventory with no host entries.
Bootstrap supplies the current effective username with Copier's `--data`; manual Copier use can do the same with
`--data "username=$(id -un)"`. Its first-copy task runs only during `copier copy`, not `copier update`. The task:

1. initializes the destination Git repository when needed;
2. uses the current short hostname unless bootstrap supplied `--host`;
3. exports the destination as `MAISON_OVERLAY_PATH`;
4. invokes `mise -C <Maison checkout> run host:add` with the generated inventory user, leaving system detection and
   validation to Maison.

The template task fails clearly when it was invoked without a Maison checkout path, so manual Copier use documents the
required `MAISON_HOME` environment variable.

## Requirements

### Functional Requirements

- Bootstrap help documents `MAISON_OVERLAY`, `--overlay`, the onboarding prompt, and the no-activation path.
- `scripts/maison_overlay.py` exposes the canonical environment precedence and supports direct local Git repositories.
- Bootstrap installs the Maison CLI before any optional overlay setup and never runs system/user activation on the no path.
- Immediate setup uses `uvx copier` through a Maison-managed `uv` installation and trusts only the checked-out local
  template source.
- The template contains `copier.yml`, generated inventory content, empty policy stubs, private-dotfile guidance, and a
  first-copy host-registration task.
- Host registration delegates to `mise run host:add` and therefore preserves repository mutation locks, schema
  validation, and platform support checks.
- Existing explicit overlays continue to use the existing bootstrap and state persistence path.

### Quality Requirements

- Add behavior-first tests for source precedence, prompt/no-prompt branching, no-activation behavior, Copier command
  construction, username seeding, template rendering, dotfile guidance, and host-task delegation.
- Do not run real Nix activation, package installation, or remote GitHub operations in tests.
- Keep user-facing errors actionable and avoid shell evaluation of untrusted overlay paths or identity values.
- Preserve private-overlay ownership and public-privacy checks.

### Compatibility and Migration Requirements

- Existing saved `overlay.toml` files remain readable.
- Existing `MAISON_OVERLAY_SOURCE` users continue to work, but new docs use `MAISON_OVERLAY`.
- Existing `--overlay` remote URLs continue to clone/update into the standard XDG data path.
- Existing `host:add` behavior remains unchanged for manually maintained overlays.
- The static-copy instructions are replaced by Copier instructions, while generated repositories retain the mirrored
  overlay layout.

## Existing Context

Maison already has a tested overlay state helper in `scripts/maison_overlay.py`, a shell adapter in
`.mise/lib/overlay.sh`, a typed inventory validator, and `mise run host:add`. The current bootstrap installs mise,
Nix/Lix, and the Maison CLI before handing control to the bootstrap task, but it requires an overlay only when
`MAISON_REQUIRE_OVERLAY` is set and otherwise silently uses public starter data. `overlay_template/` is the maintained
Copier source and contains the metadata and first-copy host-generation behavior described below.

MAISON-004 established the overlay source/state contract and MAISON-017 separated public Maison from private Terroir.
This feature extends those contracts without moving private data back into Maison.

## Proposed Design

### Bootstrap phases

Refactor `bootstrap.sh` into explicit phases while retaining its current prerequisite guards:

1. resolve or clone a Maison checkout;
2. install verified mise and link the Maison CLI;
3. resolve an explicit/saved overlay, or run interactive onboarding;
4. if onboarding is declined, print next steps and exit before Nix/system/user work;
5. if onboarding succeeds, prepare and persist the overlay;
6. install/verify Nix/Lix and execute the existing bootstrap task with the active overlay.

The overlay helper owns source parsing, local-path handling, state writes, and remote clone/update behavior. Bootstrap
owns prompts, Copier invocation, CLI installation, and phase selection.

### Copier template contract

`overlay_template/copier.yml` defines user questions for the private inventory identity and a first-copy task. Template
files use Copier's normal Jinja rendering; `inventory.toml.jinja` renders a user-only inventory, while empty mise
policies and dotfile guidance remain neutral. The task script is a private-repository file and calls Maison's public
`host:add` command with environment-provided `MAISON_HOME`, `MAISON_OVERLAY_PATH`, and optional `MAISON_HOST`.

The bootstrap path invokes Copier with the local template source and environment variables rather than a remote template,
so the setup is tied to the exact Maison checkout the user just selected. It passes the effective user with Copier's
`--data` option. `uvx copier` is run only after `mise install uv`. The generated repository is initialized before the host
mutation; committing and publishing it remain user decisions.

### State and ownership

The overlay state file continues to contain only the source and active path and remains mode `0600`. A direct local
source records that path as active; a remote source records the standard clone path. Maison remains the framework owner,
the generated repository owns user/site configuration, and Bitwarden remains the secret source of truth.

## Architecture Consistency

### Existing Patterns Reused

- Python stdlib state parsing and validation in `scripts/maison_overlay.py`.
- mise tasks as the public command surface.
- `host:add` as the single inventory mutation implementation.
- XDG state/data locations and owner-only state permissions.
- Verified artifact installation before bootstrap handoff.

### Invariants Preserved

- A file, package, service, or preference has one owner.
- Public Maison contains no personal identities or secret material.
- System activation is never attempted without an active inventory overlay on first setup.
- Host registration accepts only the supported `aarch64-darwin`, `aarch64-linux`, and `x86_64-linux` systems through
  Maison's shared `host:add` validation.
- Repository mutations are locked, validated, and recoverable.

### New Decisions Introduced

- `MAISON_OVERLAY` is the canonical environment variable; `MAISON_OVERLAY_SOURCE` is compatibility-only.
- A declined first-run overlay setup is a successful CLI-only bootstrap, not a failed setup and not an activation of
  neutral starter state.
- `overlay_template/` is a Copier template, and its first-copy task delegates host creation to Maison.

### Architecture Documentation Changes

Update reader-facing architecture/operations content to describe bootstrap phases, source precedence, Copier ownership,
and the no-overlay safety boundary.

## Operational Considerations

Immediate setup requires network access to install `uv`/Copier and the user's normal Git credentials for later remote
publishing. Declined setup is recoverable by following the printed Copier command and rerunning bootstrap with
`--overlay` or `MAISON_OVERLAY`. Updating an existing generated overlay uses `copier update`; it does not rerun host
registration automatically.

## Documentation Impact

| Documentation concern      | Exact page                                                   | Create or update        | Planned change                                                               | Owning Beads task  |
|----------------------------|--------------------------------------------------------------|-------------------------|------------------------------------------------------------------------------|--------------------|
| Introduction / usage       | `README.md`                                                  | Update                  | Replace copy instructions with Copier and explain explicit/interactive setup | `maison-mol-xke.3` |
| Operations                 | `docs/operations.md`                                         | Update                  | Document bootstrap phases, prompt outcomes, and recovery                     | `maison-mol-xke.3` |
| Host authoring             | `docs/add-a-host.md`                                         | Update                  | Explain generated host registration and manual `host:add`                    | `maison-mol-xke.3` |
| Tooling reference          | `docs/src/reference/tooling.md`                              | Update                  | Document Copier/uvx setup and template update rules                          | `maison-mol-xke.3` |
| Template                   | `overlay_template/README.md`                                 | Update                  | Make the template's Copier contract and private boundary explicit            | `maison-mol-xke.2` |
| Feature navigation         | `docs/src/SUMMARY.md`                                        | Update                  | Register this design and its delivered record                                | `maison-mol-xke.3` |
| Roadmap                    | `docs/src/planned-features.md`                               | Update                  | Add the planned feature and dependency/status entry                          | `maison-mol-xke.3` |
| Implemented Feature Record | `docs/src/features/maison-overlay-copier-bootstrap/index.md` | Create during close-out | Preserve delivery and audit history                                          | Close-out          |

## Validation Strategy

- Unit/behavior tests for overlay source precedence, direct-path state, prompt outcomes, no-activation exit, and
  bootstrap command handoff using fake `mise`, `nix`, `uvx`, and Copier executables.
- Render the Copier template in temporary directories with deterministic answers and verify inventory parsing.
- Run the generated first-copy task against a fake Maison `mise` executable and verify `host:add` receives the current
  system, hostname, user, and overlay path.
- Validate all generated TOML and public privacy boundaries.
- Run `uv run scripts/check-docs.py`, `mdbook build docs`, `mise x -- hk check`, and `mise run check`.
- Do not perform system activation, publish a remote, or modify the user's real overlay during tests.

## Implementation Decomposition

- `maison-mol-xke.1` — source precedence, prompt branches, CLI-only no path, Copier invocation, and compatibility tests.
- `maison-mol-xke.2` — template metadata, generated inventory, policy/dotfile guidance, host detection, and first-copy
  delegation tests.
- `maison-mol-xke.3` — README, operations, host authoring, tooling reference, template guide, roadmap, and navigation.

## Dependencies and Parallelism

Template implementation depends on the bootstrap contract for environment names and invocation. Documentation depends on
both code slices. Tests remain with the slice that owns the behavior; full validation follows both implementation slices.

## Rollout and Migration

Existing explicit overlays continue to work. Users without an overlay see the new prompt on the next bootstrap. Users
who decline can create an overlay later with Copier and rerun bootstrap. Existing state files and remote clone locations
remain compatible.

## Risks and Tradeoffs

- Adding Copier setup increases first-run dependencies, mitigated by using ephemeral `uvx` and keeping the no path
  available.
- A generated host mutation can fail after files render, mitigated by running it before the initial commit and printing
  the destination for repair.
- Direct local overlays alter the old clone-to-XDG behavior, but make `--overlay /path/to/repo` match its documented
  meaning and preserve remote URL cloning.
- Template task execution is intentionally limited to first copy to avoid duplicate-host failures during updates.

## Rejected Alternatives

- Keeping manual `cp -R` as the primary setup path: it does not collect identity values or perform host registration.
- Duplicating inventory mutation in the template: it would bypass Maison's validation and transaction safeguards.
- Silently continuing into neutral system activation when no overlay is supplied: it makes first-run ownership ambiguous
  and can apply unintended public starter state.
- Automatically creating a remote GitHub repository: it would require provider credentials and violate repository-choice
  boundaries.

## Open Questions

None.

## Deferred Decisions

None.

## Planning Record

### Questions Asked and Answers

- When no overlay is supplied, answering yes runs Copier-based overlay setup immediately; answering no only installs
  Maison/the CLI and points to the overlay documentation. Confirmed by the user.

### Assumptions

- The current hostname is the generated host name unless the bootstrap `--host` option overrides it.
- `MAISON_OVERLAY_HOME` is an optional local destination override for immediate setup.
- `MAISON_REQUIRE_OVERLAY=true` remains the automation/CI escape hatch for missing overlay input.

### Design Changes During Planning

- Replaced the static example-copy model with a Copier template and delegated host registration to the existing
  Maison task after the user requested automatic platform detection.

### Source Material

- Current `bootstrap.sh`, `scripts/maison_overlay.py`, `.mise/tasks/host/add`, and overlay contract tests.
- MAISON-004 private overlay design and MAISON-017 repository split design.
- User request and clarification in the current planning conversation.
