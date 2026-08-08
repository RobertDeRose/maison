# Design — MAISON-018: Cross-platform consumer bootstrap integration

## Metadata

- Beads feature root: `maison-mol-90l`
- Feature slug: `maison-018-cross-platform-bootstrap-integration`
- Design path: `docs/src/features/maison-018-cross-platform-bootstrap-integration/design.md`
- Implemented record: `docs/src/features/maison-018-cross-platform-bootstrap-integration/index.md`
- Base branch: `main`
- Status: specification review reconciled; implementation ready after reviewed commit
- Skill version evidence: `Skill version evidence: schema=dstack.skill-version.v1 skill=plan-features installed=0.8.4 canonical=unavailable status=unavailable installed_source=/Users/DeRoseR/.agents/skills/plan-features/SKILL.md checked_at=2026-08-06T15:14:37.416467Z`

## Feature Summary

Provide explicit consumer bootstrap integration tasks for both supported execution environments: Linux in an Apple
Container and macOS in a disposable Lume virtual machine. Port the unpublished consumer-side Linux integration as the
new platform-explicit Maison task, use the user's supplied Nix-prepared local Tahoe Lume image rather than pulling or
publishing a Maison image, and validate the SIP-enabled guest as part of the required delivery. The implementation also
includes a Mise-only task that installs a pinned Lume release when the macOS lane needs it; those test tasks are hidden
from the `maison` CLI wrapper.

## User Intent

The user wants the transferred existing `test:bootstrap` integration command renamed to `test:bootstrap:linux`,
wants a new `test:bootstrap:mac` command that consumes the supplied local Tahoe image. The macOS test must exercise
the real bootstrap path without changing the current Mac host. The required lane validates the SIP-enabled guest;
the former separate SIP lane remains reserved but is not required. Lume installation belongs to an explicit Mise
test-task dependency, not to the public `maison` command surface.

## Goals

- Expose `test:bootstrap:linux` for the existing disposable Apple Container bootstrap test.
- Expose `test:bootstrap:mac` for full bootstrap validation in a disposable Apple Silicon macOS VM.
- Use the pinned Maison revision from the consumer lock for both lanes.
- Use the supplied local Nix-prepared Lume VM `macos-tahoe-with-nix` through Lume for the macOS lane, with a
  base-name override for another stopped local copy.
- Keep consumer staging, credentials, SSH, VM/container lifecycle, and cleanup owned by the Maison test harness.
- Make the exact immutable source and artifact contracts executable without requiring implementation-time policy choices.
- Make successful and interrupted runs unable to modify the production host, production inventory, or private source.
- Verify the supplied SIP-enabled macOS image as part of the required lane; do not publish or delete that user-owned
  base.

## Non-Goals

- Building or publishing a Maison-owned macOS VM image.
- Running Darwin activation against the current macOS host, even under a temporary host account.
- Copying Maison implementation, schemas, private Git objects, credentials, private keys, or a duplicate product test suite into a consumer.
- Changing Maison's public CLI semantics beyond adding hidden test-task support; the reviewed bootstrap source-branch
  detection and explicit macOS branch-test override are included in this follow-up.
- Making the SIP-enabled lane a prerequisite for the first macOS lane or for feature close-out.
- Resolving an upstream Linux `system-manager` permission failure discovered while executing the consumer lane; record it as related Maison validation evidence if it remains.

## User-Facing Behavior

The supported commands are:

```bash
mise run test:bootstrap:linux
mise run test:bootstrap:mac
```

The existing `test:deploy` command remains a Linux deployment integration test and is not renamed. These test tasks
are invoked directly through Mise; they are intentionally absent from the `maison` wrapper's public command surface.
The SIP command name is reserved by the deferred Beads child, but no `test:bootstrap:mac-sip` task is shipped before
that child is activated. The reserved command is not required to run or pass before the feature's required
implementation can be delivered.

## Requirements

### Functional Requirements

1. Maison provides hidden Mise tasks for `test:bootstrap:linux` and `test:bootstrap:mac`; they are available through
   direct `mise run` but are not resolvable, listed, or documented through the `maison` CLI wrapper. The SIP command
   name is reserved in Beads and is not shipped until its deferred child is activated.
2. A hidden macOS test dependency installs Lume 0.5.1 from the pinned `trycua/cua` Darwin arm64 archive, verifies
   the mandatory SHA-256 digest, verifies `lume --version`, installs only under a versioned host-user data directory,
   and is idempotent. It is not run by public bootstrap, apply, deploy, or other Maison CLI commands.
3. The Linux integration task is a new `.mise/tasks/test/bootstrap/linux` task; the existing `.mise/tasks/bootstrap`
   normal consumer bootstrap task is unchanged. All reader-facing references use `test:bootstrap:linux`; no supported
   documentation claims that the unqualified integration command exists.
4. The Linux task retains the transferred pinned Maison bootstrap behavior, committed-content consumer stage, token
   handling, public-key-only SSH behavior, disposable Apple Container lifecycle, convergence assertions, and
   interruption cleanup.
5. The macOS task requires Lume 0.5.1 on Apple Silicon, uses the supplied local Nix-prepared Lume base
   `macos-tahoe-with-nix` (or its configured stopped copy), and clones a uniquely named worker from that base for each
   run.
6. The macOS task runs headlessly through Lume's VM/SSH interface, stages a disposable committed-content consumer
   with a temporary `aarch64-darwin` host and test user, and invokes the public Maison bootstrap script at the full
   locked revision after validating its GitHub blob identity.
7. The macOS task verifies the selected Maison revision, the supplied guest identity and `csrutil status: enabled`,
   Nix-Darwin/system convergence, mise/fnox/Maison user convergence, UTF-8 locale state, and disposable host identity.
8. Both required lanes delete or stop their disposable resources and remove staging, token, temporary SSH key, and
   downloaded-script material on success, failure, and interruption.
9. The former future SIP lane remains represented as a deferred Beads child, but the required macOS lane now asserts
   the supplied SIP-enabled guest state directly; the child has no blocking edge into the required Linux or macOS lane.

### Quality Requirements

- Never pipe an unreviewed or network-downloaded script into a shell; download the exact locked Maison revision by
  default (or an explicitly selected, resolved branch ref for branch testing) and the pinned prerequisite artifacts to
  files, validate them, then execute them.
- Never mount or copy a host private SSH key; generate a temporary host key when needed and transfer only its public
  half into a disposable guest.
- Keep GitHub tokens out of repositories, command-line arguments, logs, and committed test artifacts.
- Require a clean consumer Git checkout and materialize only committed content with `git archive`; never stage the
  source `.git`, `.beads`, ignored files, local fnox material, or build results.
- Validate VM/image identity, host names, addresses, and paths before interpolation into inventory or remote commands.
- Use the named local VM, fixed guest version/build, pinned Lume artifact, and Maison revision values for reproducible
  evidence; never infer identity from a floating image tag.
- Assert the supplied base's expected macOS build, installed Nix daemon, `xcode-select`, SSH/unattended-login state,
  and SIP status before running bootstrap; final verification must confirm Command Line Tools after bootstrap.

### Compatibility and Migration Requirements

- Existing Linux users must replace `mise run test:bootstrap` with `mise run test:bootstrap:linux`.
- Existing `mise run test:deploy` behavior remains unchanged except for shared helper refactoring required by the
  platform-specific bootstrap tasks.
- The public documentation must explain that the macOS image is a user-supplied local Lume base with known version,
  build, SSH, unattended-login, and SIP preconditions, rather than a Maison-built or task-published image.

## Existing Context

Maison currently has deterministic repository tests and the consumer/bootstrap/runtime task surfaces, but no
platform-specific consumer integration task group. The Linux and deployment source to reconcile is the immutable
Terroir commit `2e61be6d32e17911a2dd162ecf9eed3b4dedacbe`, specifically `.mise/lib/consumer-integration.sh`,
`.mise/tasks/test/bootstrap`, `.mise/tasks/test/deploy`, and `.mise/tasks/test/image`. That commit is source material
only: the harness is ported into Maison and no Terroir checkout, private Git history, or consumer-side duplicate test
suite becomes a Maison runtime dependency. The consumer remains an external input selected through
`MAISON_CONSUMER_ROOT`; Maison must not copy the consumer's private Git history or make Terroir a required checkout
for its normal test suite.

Maison owns the bootstrap script, runtime tasks, schemas, reusable orchestration, platform test harness, and test-task
installation dependencies. A consumer owns its inventory, host modules, and configuration. The current production
macOS host must never be used as the test target.

Lume provides local Apple Virtualization.framework VMs on Apple Silicon. The supplied local Tahoe VM reports
macOS 26.6.1/build 25G76, an installed Nix daemon, SSH, unattended login, and SIP enabled. It may not contain Command
Line Tools or passwordless sudo, so the worker prepares only its disposable privilege boundary and installs the tools
before the pinned bootstrap runs; final verification confirms the tools.

## Proposed Design

### Hidden Mise task surface

Add hidden task files under Maison's `.mise/tasks/test/` tree for `test:bootstrap:linux`, `test:deploy`,
`test:image`, `test:lume:install`, and `test:bootstrap:mac`. The task files remain directly invocable with
`mise -C "$MAISON_HOME" run ...`, while `bin/maison` filters every `test:*` name from command resolution,
completion, help, and the no-argument `maison tasks` listing. `maison tasks` prints the same public task listing as
help and rejects listing flags that could expose hidden tasks; direct `mise -C "$MAISON_HOME" tasks --hidden` is the
internal discovery path. The reserved SIP command has no task file until the deferred child is activated.

### Lume installation dependency

Add hidden `test:lume:install` as a dependency of `test:bootstrap:mac`. The exact artifact contract is:

- Release `lume-v0.5.1` from `trycua/cua`.
- Darwin arm64 archive `lume-0.5.1-darwin-arm64.tar.gz`.
- URL `https://github.com/trycua/cua/releases/download/lume-v0.5.1/lume-0.5.1-darwin-arm64.tar.gz`.
- SHA-256 `7f10cfbe66a800f98a5db88129f7dc024600fcdc139e0be124845bc7a3dc1359`.
- The release manifest is the upstream checksum authority; the checked-in task contract repeats the digest so
  verification does not depend on a mutable API response.
- The archive's top-level `lume` executable is installed atomically at
  `${XDG_DATA_HOME:-$HOME/.local/share}/maison/lume/0.5.1/lume`, with a stable user-owned path used by the macOS
  task. No system package, global PATH edit, launch agent, or privileged installer is used.

The task must require Apple Silicon macOS 13 or newer, download to a mode-0700 temporary directory, verify the exact
SHA-256 before extraction, use a lock directory for concurrent invocations, preserve a verified existing install,
verify `lume --version` reports `0.5.1`, and fail rather than replace an incompatible existing `lume`. It must never
use the upstream `curl | bash` installer, must be idempotent, and must print host-side installation and recovery
instructions. It is never pulled into ordinary `maison` workflows.

### Linux lane

Port the source files from Terroir commit `2e61be6d32e17911a2dd162ecf9eed3b4dedacbe` into Maison's `.mise/lib/`
and `.mise/tasks/test/` paths. The new `.mise/tasks/test/bootstrap/linux` task is the explicit Linux integration
entry point; `.mise/tasks/bootstrap` remains the normal consumer bootstrap task. Keep `test:deploy` and `test:image`
hidden, use `MAISON_CONSUMER_ROOT` or an explicit consumer argument, and preserve the transferred Apple Container
lifecycle and convergence assertions. The shared helper owns committed-content staging, exact lock-node parsing, and
bootstrap-script blob verification for both platform lanes. The known `system-manager` failure is validation evidence,
not an implementation prerequisite.

### macOS lane

Add a platform-specific task and a small Lume helper layer. The task will:

1. Resolve the external consumer with Maison's existing consumer-root guard and parse `nodes.maison.locked` from its
   `flake.lock`; require `type=github`, `owner=RobertDeRose`, `repo=maison`, and a full 40-character `rev`.
2. Require the verified Lume 0.5.1 executable, `jq`, `git`, `ssh`, `ssh-keygen`, `tar`, `curl`, and the existing
   consumer/staging prerequisites.
3. Resolve the supplied local Lume base from `MAISON_MACOS_BASE_NAME` or the default `macos-tahoe-with-nix`; fail
   clearly when it is absent, stop it for inspection, and never pull, publish, or delete it. Verify macOS
   26.6.1/build 25G76, the installed Nix daemon, `xcode-select`, SSH, unattended login, and `csrutil status` reports
   enabled before cloning. The base may lack `/Library/Developer/CommandLineTools` and passwordless sudo; the worker
   prepares its disposable privilege boundary, installs the tools, and final verification confirms them.
4. Clone the stopped base into a unique worker, boot it with `lume run <worker> --detach --display none`, and obtain
   its address from `lume get <worker> --format json`.
5. Use the disposable `lume` account/password to grant passwordless sudo only to the disposable `lume` and `tester`
   accounts, create the test user, and install missing Command Line Tools. Then generate a temporary host SSH key pair
   and install its public half. Use noninteractive SSH/SCP with the temporary private key; the private key never enters
   the guest or logs.
6. Copy a deterministic committed-content consumer stage into the guest. The stage adds only a test user and a
   temporary Darwin host, and uses no production host record, private endpoint, or source `.git` directory.
7. Download `bootstrap.sh` from the public GitHub contents/raw endpoints at the full locked revision by default.
   Compare the GitHub blob SHA returned for `bootstrap.sh` with `git hash-object` of the downloaded file before
   execution, then run it with `--consumer`, `--host`, `--repo`, and the locked `--ref`. For reviewed branch testing,
   `MAISON_MACOS_BOOTSTRAP_REF` (or the `feat/test-bootstrap-macos` checkout default) resolves the branch head,
   verifies the branch blob, and passes that branch through the same bootstrap clone path. A missing/unpublished ref
   fails clearly.
8. Run verification in the guest, including selected Maison `HEAD`, `sw_vers`, `csrutil status: enabled`, Nix-Darwin/system
   convergence, mise/fnox/Maison user convergence, UTF-8 locale, and expected disposable host identity. Write only
   sanitized result output to the host log.
9. Shut down/stop and delete the worker, remove host-side stage, token, temporary key, and downloaded script files, and
   clean up on signals.

The test uses the supplied local image's disposable `lume` account and keeps all privilege setup and test-user
creation inside the disposable worker. No host sudoers, account, defaults, launchd, Nix, Homebrew, or other production
state may change. The user-owned base is never deleted or published by the task. Lume itself may be installed on the host only by the explicit hidden Mise
dependency described above.

### SIP lane

Reserve `test:bootstrap:mac-sip` as a deferred child and do not ship a task file until that child is activated. When
activated, it may provide separate SIP-focused coverage. The required macOS lane already uses the supplied
SIP-enabled base and verifies that state before and after bootstrap.

## Architecture Consistency

### Existing Patterns Reused

- Maison remains the owner of bootstrap, validation, flake modules, and activation orchestration.
- The transferred deterministic stage, full-lock revision resolution, token-file, and signal-cleanup patterns are
  reused.
- Disposable named resources are created outside the production inventory and verified before assertion.
- Consumer stages are materialized from committed Git content outside the source checkout; generated test inventory is
  added only after the source archive is created.
- Reader-facing behavior is documented in operations/reference pages rather than in implementation notes alone.

### Invariants Preserved

- No production activation from tests.
- No private Git history, credentials, private keys, or Maison internals cross the consumer boundary.
- A full immutable Maison revision is required by default; branch testing resolves and records the selected branch head
  before execution.
- Cleanup is safe on success, failure, and interruption.
- The public consumer remains self-contained and does not require a published Terroir remote.

### New Decisions Introduced

- Platform is part of the bootstrap task name: `test:bootstrap:linux` and `test:bootstrap:mac`.
- The required macOS base is the user-supplied local Tahoe VM rather than a pulled or Maison-published image.
- Lume 0.5.1 is a verified, host-user installation dependency with a checked-in archive digest.
- The required macOS lane asserts the supplied base is SIP-enabled; the reserved SIP child does not add a second
  required task.
- The macOS lane remains immutable by default while allowing an explicit, resolved branch ref for reviewed bootstrap
  testing.

### Architecture Documentation Changes

Update Maison's operations and task-reference documentation to define the hidden integration-task boundary and the
consumer input contract. No new architecture page is required.

## Operational Considerations

The macOS lane is local Apple Silicon infrastructure and can install Lume 0.5.1 through its explicit hidden Mise
prerequisite. It requires macOS 13 or newer, sufficient host disk/memory, `jq`, and the user-supplied local Tahoe VM.
The base VM is host-local test infrastructure and is never deleted or published by the task. Each worker is single-use
and must be deleted even after failed bootstrap. Lume telemetry should be disabled for privacy-sensitive runs. Standard
CI runners are not assumed to support nested macOS virtualization. The installer uses the versioned archive and digest
recorded in this design rather than the upstream shell installer.

## Documentation Impact

| Documentation concern        | Exact page                                                                     | Create or update     | Planned change                                                                                                                                            | Owning Beads task                  |
|------------------------------|--------------------------------------------------------------------------------|----------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------|
| Documentation concern        | Exact page                                                                     | Create or update     | Planned change                                                                                                                                            | Owning Beads task                  |
| ---------------------------- | ------------------------------------------------------------------------------ | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------                        | --------------------               |
| Usage / Operations           | `docs/operations.md`                                                           | Update               | `.1` owns the hidden-task/Lume host-prerequisite section; `.2` owns the Linux integration section; `.3` owns macOS image, VM, SIP, and cleanup sections.  | `.1`, `.2`, `.3`                   |
| Navigation wrapper           | `docs/src/operations.md`                                                       | No direct content    | Include-only wrapper; validate navigation after the root operations page changes.                                                                         | `.2`, `.3`                         |
| Development                  | `docs/src/development/tooling.md`                                              | Update               | Document direct Mise invocation, hidden-task filtering, pinned Lume artifact, and Apple Silicon prerequisites.                                            | `maison-mol-4pv.1`                 |
| Reference                    | `docs/task-reference.md`                                                       | Update               | `.1` owns public listing/hidden-boundary sections; `.2` owns Linux task arguments/contracts; `.3` owns macOS image/VM contracts and deferred SIP wording. | `.1`, `.2`, `.3`                   |
| Navigation wrapper           | `docs/src/task-reference.md`                                                   | No direct content    | Include-only wrapper; validate navigation after the root task-reference page changes.                                                                     | `maison-mol-4pv.1`                 |
| Reference                    | `docs/src/reference/tooling.md`                                                | Update               | Add test-task dependency, staging, artifact, and validation contracts.                                                                                    | `maison-mol-4pv.1`                 |
| Navigation                   | `docs/src/SUMMARY.md`                                                          | Update               | Register the design now and the implemented record during close-out.                                                                                      | `maison-mol-o5z`, `maison-mol-55k` |
| Planned Features             | `docs/src/planned-features.md`                                                 | Update               | Add MAISON-018 roadmap entry and reconcile its delivered state during close-out.                                                                          | `maison-mol-o5z`, `maison-mol-55k` |
| Implemented-feature index    | `docs/src/features/index.md`                                                   | Update close-out     | Add the delivered feature record to the reader-facing implemented-feature index.                                                                          | `maison-mol-55k`                   |
| Implemented Feature Record   | `docs/src/features/maison-018-cross-platform-bootstrap-integration/index.md`   | Create close-out     | Record delivery, deferred SIP lane, documentation, and validation evidence.                                                                               | `maison-mol-55k`                   |

## Validation Strategy

- Run task-contract tests for every hidden task, verify direct `mise run` availability, and verify `test:*` names are
  absent from `maison`, `maison help`, `maison tasks`, and generated completions. Verify `mise tasks --hidden` remains
  the only hidden listing path.
- Run the Lume installer task on Apple Silicon and verify the pinned archive digest, version, user-local install,
  incompatible-version failure, and idempotent/concurrent behavior without using the upstream shell installer.
- Run `bash -n`, ShellCheck, and shfmt on all new/changed shell files.
- Run `mise run consumer:validate`, `python3 scripts/check-docs.py`, `mise run check`, and `git diff --check`.
- In a prepared Apple Container environment, run `mise run test:bootstrap:linux` and `mise run test:deploy`; record
  the known `system-manager` blocker as external evidence if it remains, without treating it as an implementation
  dependency.
- In a prepared Apple Silicon host, run `mise run test:bootstrap:mac` and inspect base-image assertions, worker
  deletion, staging/token/key cleanup, and injected failure/interruption paths.
- Verify GitHub blob identity for the downloaded bootstrap script and verify logs/staged artifacts contain no token,
  private key, private endpoint, or host repository path.
- Do not run the reserved deferred SIP command during required feature validation.

## Implementation Decomposition

1. Add the hidden Mise task surface, public-list filtering, pinned Lume artifact, and tooling/reference docs
   (`maison-mol-4pv.1`).
2. Port the immutable Terroir source commit's Linux bootstrap/deployment harness, shared committed-content staging,
   bootstrap blob verification, and Linux operations docs under Maison (`maison-mol-4pv.2`).
3. Add the Lume macOS bootstrap task, VM lifecycle helper, macOS operations docs, and platform-specific contract tests;
   it follows `.2` because it consumes the shared staging/source-verification helper (`maison-mol-4pv.3`).
4. Keep the SIP command reserved as an explicitly deferred Beads child; do not add a task file or required validation
   until it is activated (`maison-mol-4pv.4`).

## Dependencies and Parallelism

The Linux child records the known upstream system-manager failure as validation evidence but does not depend on the
open bug; an open `related`/`discovered-from` relationship preserves provenance without blocking implementation. The
Lume installer and hidden CLI-boundary tasks precede the Linux lane so shared operations/task-reference edits are
serialized. `.2` owns `.mise/lib/consumer-integration.sh`, committed-content staging, lock parsing, bootstrap blob
verification, and Linux task files; `.3` owns the Lume VM helper, macOS task, and macOS-specific tests/docs. Each
implementation child makes one isolated commit containing only its owned source, tests, and documentation sections:
`.1` then `.2` then `.3`; no child reformats or edits another child's sections. `.3` depends on `.2` for the shared
helper. The SIP child is deferred, has no task file before activation, and does not block required children or the
implementation coordinator.

## Rollout and Migration

Update local scripts and documentation that previously referred to the transferred consumer integration task to call
`test:bootstrap:linux`. Do not retain an alias for that integration task; the explicit rename is intended to remove
platform ambiguity. The normal Maison `bootstrap` task is unchanged. The macOS task is opt-in and does not alter
production activation or default repository checks.

## Risks and Tradeoffs

- The supplied local base is SIP-enabled and Nix-prepared, but may lack Command Line Tools and passwordless sudo; the
  worker grants passwordless sudo only to its disposable `lume` and `tester` accounts, creates the test user, installs
  the tools, and verifies them before convergence assertions.
- Installing Lume from a Mise task mutates host tooling and must remain opt-in, pinned, checksum-verified, and hidden
  from the public Maison CLI.
- Nix-Darwin builds make the macOS lane slower than the container lane, even though the local base avoids a large image
  pull.
- Lume and macOS guest support are host-local and cannot be assumed in ordinary hosted CI.
- The local VM and Lume behavior are host-local dependencies; a fixed guest version/build and preflight assertions
  limit drift.
- Homebrew/system-extension behavior in the macOS profile may require a prepared guest or visible first-run setup;
  the task must fail clearly rather than modify the host to compensate.

## Rejected Alternatives

- Running full Darwin bootstrap as a temporary user on the current host: a user account does not isolate Nix, Homebrew,
  launchd, system defaults, or other privileged state.
- Building a Maison-owned macOS image: it duplicates upstream image maintenance and violates the chosen public-base
  boundary.
- Using an unverified network-piped script or an unresolved Maison branch: these do not provide an auditable bootstrap
  or host-tooling input. Branch testing must use the verified file and resolved head path described above.
- Making a second SIP-enabled task a prerequisite: the supplied image already provides SIP-enabled coverage in the
  required lane.

## Open Questions

None required for the first implementation lanes.

## Deferred Decisions

- Any future SIP-specific guest preparation remains owned by the deferred SIP child; it must not change the current
  host or duplicate the required local-image lane.

## Specification Review Reconciliation

The first four-role review run used packet `packet-maison-018-r1` at the planning commit. The documentation review was
approved. Architecture, simplicity, and execution findings were reconciled in this design and the Beads graph:

- Public task hiding now covers resolver, help, completion, and `maison tasks`; direct hidden discovery remains a Mise
  operation only.
- The Linux task is explicitly new and ported from Terroir commit
  `2e61be6d32e17911a2dd162ecf9eed3b4dedacbe`; the normal `.mise/tasks/bootstrap` task remains unchanged.
- Lume is pinned to release `0.5.1`, a named Darwin arm64 archive, and a checked-in SHA-256 digest with user-local
  atomic installation and incompatible-version failure behavior.
- The full Maison lock node and GitHub `bootstrap.sh` blob identity are required before bootstrap execution.
- Consumer stages use clean committed Git content, never the source repository's private or mutable state.
- The required macOS lane asserts the supplied local base is SIP-enabled; the SIP command remains reserved and absent
  until any future separate coverage is activated.
- The Linux upstream bug is related provenance/validation evidence, not an implementation blocking edge. Shared helper
  and documentation ownership is sequenced explicitly between implementation children.

### Post-delivery contract revision — 2026-08-07

The user explicitly superseded the original published-Trycua image contract after the current host could not complete
that image pull. The macOS task now consumes the user-owned Nix-prepared local Lume VM `macos-tahoe-with-nix` by default, accepts
`MAISON_MACOS_BASE_NAME` for another stopped local copy, and never pulls, publishes, or deletes the base. The verified
local guest contract is macOS 26.6.1/build 25G76, an installed Nix daemon, SSH and unattended login available, and SIP
enabled. Command Line Tools and passwordless sudo are allowed to be absent at base preflight: the worker prepares its
own disposable `lume` privilege boundary, creates the test user, installs Command Line Tools, and final worker
verification requires `/Library/Developer/CommandLineTools`.

This revision supersedes the earlier Trycua `macos-tahoe-cua:26.5.2`/build `25F84` and SIP-disabled assumptions for the
implemented task. The historical planning record below remains unchanged as an audit of the original decision.

### Planning Record

### Questions Asked and Answers

- User requested the existing task be renamed to `test:bootstrap:linux`.
- User requested a new `test:bootstrap:mac` task.
- User requested an SIP-enabled lane be tracked as future deferred work inside the epic, not required outside it.
- User selected Trycua's published Tahoe Lume image instead of creating a Maison-owned image.

### Assumptions

- The current pinned Maison revision remains the bootstrap source for both lanes.
- `macos-tahoe-cua:26.5.2` remains available through Trycua's Lume/OCI registry contract when implementation starts.
- The hidden Mise test dependency installs Lume only when the macOS test task needs it; public Maison workflows never
  invoke that dependency.

### Design Changes During Planning

- The initial macOS proposal used a temporary account on the current host; it was rejected because user isolation does
  not isolate privileged Darwin activation.
- The macOS strategy changed to a disposable Lume worker using Trycua's published Tahoe base.
- The integration epic moved from the consumer repository to Maison so the framework owns the reusable harness, Lume
  installation dependency, and hidden Mise task surface.
- Specification review defined public task-list filtering, immutable bootstrap blob verification, committed-content
  staging, the Lume 0.5.1 artifact contract, the external Linux blocker direction, and the deferred SIP command
  behavior.

### Source Material

- Terroir integration source commit `2e61be6d32e17911a2dd162ecf9eed3b4dedacbe` and its four harness paths listed in
  Existing Context.
- Maison `bootstrap.sh`, `system:apply`, `bin/maison`, and existing Mise task conventions.
- Maison's consumer contract, test suite, and Darwin profile modules.
- Trycua Lume installation documentation: `https://cua.ai/docs/how-to-guides/lume/install-lume`.
- Trycua Lume VM documentation: `https://cua.ai/docs/how-to-guides/driver/run-in-macos-lume-vm`.
- Trycua Lume CLI documentation: `https://cua.ai/docs/reference/lume/cli-reference`.
- Trycua release `trycua/cua:lume-v0.5.1` and its `release-manifest.json` SHA-256 evidence.
