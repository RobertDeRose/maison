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
new platform-explicit Maison task, use Trycua's published Tahoe image rather than maintaining a Maison VM image, and
record a future SIP-enabled macOS lane without making it part of the required delivery. The implementation also
includes a Mise-only task that installs a pinned Lume release when the macOS lane needs it; those test tasks are hidden
from the `maison` CLI wrapper.

## User Intent

The user wants the transferred existing `test:bootstrap` integration command renamed to `test:bootstrap:linux`,
wants a new `test:bootstrap:mac` command, and wants an SIP-enabled lane tracked as deferred work inside the same
feature epic.
The macOS test must exercise the real bootstrap path without changing the current Mac host. A prebuilt Trycua Lume
image is preferred over creating or maintaining a Maison-owned image. Lume installation belongs to an explicit Mise
test-task dependency, not to the public `maison` command surface.

## Goals

- Expose `test:bootstrap:linux` for the existing disposable Apple Container bootstrap test.
- Expose `test:bootstrap:mac` for full bootstrap validation in a disposable Apple Silicon macOS VM.
- Use the pinned Maison revision from the consumer lock for both lanes.
- Use the published, versioned `macos-tahoe-cua:26.5.2` Trycua image through Lume for the macOS lane.
- Keep consumer staging, credentials, SSH, VM/container lifecycle, and cleanup owned by the Maison test harness.
- Make the exact immutable source and artifact contracts executable without requiring implementation-time policy choices.
- Make successful and interrupted runs unable to modify the production host, production inventory, or private source.
- Track an SIP-enabled macOS lane as an explicitly deferred child task that does not block the required lanes or epic.

## Non-Goals

- Building or publishing a Maison-owned macOS VM image.
- Running Darwin activation against the current macOS host, even under a temporary host account.
- Copying Maison implementation, schemas, private Git objects, credentials, private keys, or a duplicate product test suite into a consumer.
- Changing Maison's core bootstrap or public CLI command semantics beyond adding hidden test-task support.
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
5. The macOS task requires Lume 0.5.1 on Apple Silicon, uses the versioned Trycua image
   `macos-tahoe-cua:26.5.2`, and clones a uniquely named worker from a stopped base VM for each run.
6. The macOS task runs headlessly through Lume's VM/SSH interface, stages a disposable committed-content consumer
   with a temporary `aarch64-darwin` host and test user, and invokes the public Maison bootstrap script at the full
   locked revision after validating its GitHub blob identity.
7. The macOS task verifies the locked Maison revision, the published guest identity and `csrutil status: disabled`,
   Nix-Darwin/system convergence, mise/fnox/Maison user convergence, UTF-8 locale state, and disposable host identity.
8. Both required lanes delete or stop their disposable resources and remove staging, token, temporary SSH key, and
   downloaded-script material on success, failure, and interruption.
9. The future SIP lane is represented as a deferred Beads child with an acceptance contract for the same bootstrap
   assertions under SIP-enabled guest state; it has no blocking edge into the required Linux or macOS lane.

### Quality Requirements

- Never pipe an unreviewed, floating, or network-downloaded script into a shell; download the exact locked Maison
  revision and the pinned prerequisite artifacts to files, validate them, then execute them.
- Never mount or copy a host private SSH key; generate a temporary host key when needed and transfer only its public
  half into a disposable guest.
- Keep GitHub tokens out of repositories, command-line arguments, logs, and committed test artifacts.
- Require a clean consumer Git checkout and materialize only committed content with `git archive`; never stage the
  source `.git`, `.beads`, ignored files, local fnox material, or build results.
- Validate VM/image identity, host names, addresses, and paths before interpolation into inventory or remote commands.
- Use versioned image, VM, Lume artifact, and Maison revision values, never `latest`, for reproducible evidence.
- Assert the published base's expected macOS build, Command Line Tools path, SSH/unattended-login state, and SIP
  status before running bootstrap.

### Compatibility and Migration Requirements

- Existing Linux users must replace `mise run test:bootstrap` with `mise run test:bootstrap:linux`.
- Existing `mise run test:deploy` behavior remains unchanged except for shared helper refactoring required by the
  platform-specific bootstrap tasks.
- The public documentation must explain that the macOS image is a published Trycua base with known preconditions,
  including its SIP state, rather than a Maison-built pristine image.

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

Lume provides local Apple Virtualization.framework VMs on Apple Silicon. Trycua documents the public versioned image
`macos-tahoe-cua:26.5.2`, which supplies a Tahoe guest with Command Line Tools, SSH, and unattended login setup.
That base has SIP disabled; this is recorded as a precondition for the required lane and is not silently presented as
SIP-on coverage.

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
3. Use `lume pull macos-tahoe-cua:26.5.2 <base-name>` only when the exact host-local base is absent; stop and inspect
   the base without mutating it. Verify macOS 26.5.2/build 25F84, `/Library/Developer/CommandLineTools`, SSH,
   unattended login, and `csrutil status` reports disabled before cloning.
4. Clone the stopped base into a unique worker, boot it with `lume run <worker> --detach --display none`, and obtain
   its address from `lume get <worker> --format json`.
5. Generate a temporary host SSH key pair, use the published `lume` account/password only to install the public key,
   then use noninteractive SSH/SCP with the temporary private key. The private key never enters the guest or logs.
6. Copy a deterministic committed-content consumer stage into the guest. The stage adds only a test user and a
   temporary Darwin host, and uses no production host record, private endpoint, or source `.git` directory.
7. Download `bootstrap.sh` from the public GitHub contents/raw endpoints at the locked revision. Compare the GitHub
   blob SHA returned for `bootstrap.sh` with `git hash-object` of the downloaded file before execution, then run it
   with `--consumer`, `--host`, `--repo`, and the full locked `--ref`. A missing/unpublished revision fails clearly.
8. Run verification in the guest, including locked Maison `HEAD`, `sw_vers`, `csrutil status: disabled`, Nix-Darwin/system
   convergence, mise/fnox/Maison user convergence, UTF-8 locale, and expected disposable host identity. Write only
   sanitized result output to the host log.
9. Shut down/stop and delete the worker, remove host-side stage, token, temporary key, and downloaded script files, and
   clean up on signals.

The test uses the published image's disposable `lume` account and keeps all privilege setup inside the worker. No host
sudoers, account, defaults, launchd, Nix, Homebrew, or other production state may change. Lume itself may be installed
on the host only by the explicit hidden Mise dependency described above.

### SIP lane

Reserve `test:bootstrap:mac-sip` as a deferred child and do not ship a task file until that child is activated. When
activated, it will use a SIP-enabled disposable macOS worker and repeat the required macOS assertions, including
`csrutil status` enabled before and after the run. Its guest source/preparation may be selected when the task is
activated, but the required feature lanes do not depend on it and the first macOS lane explicitly reports that it is
SIP-disabled.

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
- A full immutable Maison revision is required.
- Cleanup is safe on success, failure, and interruption.
- The public consumer remains self-contained and does not require a published Terroir remote.

### New Decisions Introduced

- Platform is part of the bootstrap task name: `test:bootstrap:linux` and `test:bootstrap:mac`.
- The required macOS base is the published, versioned Trycua Tahoe image rather than a Maison-built image.
- Lume 0.5.1 is a verified, host-user installation dependency with a checked-in archive digest.
- The required macOS lane asserts the published base is SIP-disabled; SIP-enabled coverage is deferred and does not
  block the first macOS lane.

### Architecture Documentation Changes

Update Maison's operations and task-reference documentation to define the hidden integration-task boundary and the
consumer input contract. No new architecture page is required.

## Operational Considerations

The macOS lane is local Apple Silicon infrastructure and can install Lume 0.5.1 through its explicit hidden Mise
prerequisite. It requires macOS 13 or newer, sufficient host disk/memory, `jq`, and the versioned Trycua image. The
base VM is host-local test infrastructure and must remain stopped and unmodified. Each worker is single-use and must
be deleted even after failed bootstrap. Lume telemetry should be disabled for privacy-sensitive runs. Standard CI
runners are not assumed to support nested macOS virtualization. The installer uses the versioned archive and digest
recorded in this design rather than the upstream shell installer.

## Documentation Impact

| Documentation concern      | Exact page                                                                   | Create or update | Planned change                                                                                                            | Owning Beads task  |
|----------------------------|------------------------------------------------------------------------------|------------------|---------------------------------------------------------------------------------------------------------------------------|--------------------|
| Usage / Operations         | `docs/src/operations.md`                                                     | Update           | `.1` documents host Lume installation; `.2` owns Linux integration; `.3` owns macOS image, VM, SIP, and cleanup sections. | `.1`, `.2`, `.3`   |
| Development                | `docs/src/development/tooling.md`                                            | Update           | Document direct Mise invocation, hidden-task filtering, pinned Lume artifact, and Apple Silicon prerequisites.            | `maison-mol-4pv.1` |
| Reference                  | `docs/src/task-reference.md`                                                 | Update           | Define public task listing, direct Mise task names, arguments, image/version contracts, and deferred SIP behavior.        | `.1`, `.2`, `.3`   |
| Reference                  | `docs/src/reference/tooling.md`                                              | Update           | Add test-task dependency, staging, artifact, and validation contracts.                                                    | `maison-mol-4pv.1` |
| Navigation                 | `docs/src/SUMMARY.md`                                                        | Update           | Register the feature design.                                                                                              | `maison-mol-o5z`   |
| Planned Features           | `docs/src/planned-features.md`                                               | Update           | Add MAISON-018 roadmap entry and dependency status.                                                                       | `maison-mol-o5z`   |
| Implemented Feature Record | `docs/src/features/maison-018-cross-platform-bootstrap-integration/index.md` | Create close-out | Record delivery, deferred SIP lane, and evidence.                                                                         | `maison-mol-55k`   |

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
Lume installer and hidden CLI-boundary tasks precede the macOS lane. `.2` owns `.mise/lib/consumer-integration.sh`,
committed-content staging, lock parsing, bootstrap blob verification, and Linux task files; `.3` owns the Lume VM
helper, macOS task, and macOS-specific tests/docs. `.3` depends on `.2` for the shared helper. The SIP child is
deferred, has no task file before activation, and does not block required children or the implementation coordinator.

## Rollout and Migration

Update local scripts and documentation that previously referred to the transferred consumer integration task to call
`test:bootstrap:linux`. Do not retain an alias for that integration task; the explicit rename is intended to remove
platform ambiguity. The normal Maison `bootstrap` task is unchanged. The macOS task is opt-in and does not alter
production activation or default repository checks.

## Risks and Tradeoffs

- The Trycua base is SIP-disabled, so the required lane does not prove SIP-on behavior.
- Installing Lume from a Mise task mutates host tooling and must remain opt-in, pinned, checksum-verified, and hidden
  from the public Maison CLI.
- Large VM pulls and Nix-Darwin builds make the macOS lane slower than the container lane.
- Lume and macOS guest support are host-local and cannot be assumed in ordinary hosted CI.
- VM image tags and Lume behavior are external dependencies; versioned tags and preflight assertions limit drift.
- Homebrew/system-extension behavior in the macOS profile may require a prepared guest or visible first-run setup;
  the task must fail clearly rather than modify the host to compensate.

## Rejected Alternatives

- Running full Darwin bootstrap as a temporary user on the current host: a user account does not isolate Nix, Homebrew,
  launchd, system defaults, or other privileged state.
- Building a Maison-owned macOS image: it duplicates upstream image maintenance and violates the chosen public-base
  boundary.
- Using `curl | bash`, a floating Maison branch, or an unverified release API response: these do not provide an
  auditable bootstrap or host-tooling input.
- Making SIP-enabled coverage a prerequisite: it would delay the useful published-base lane and is explicitly deferred.

## Open Questions

None required for the first implementation lanes.

## Deferred Decisions

- The exact SIP-enabled guest preparation method is owned by the deferred SIP child; it must produce an SIP-enabled
  worker without changing the current host and must not block the required macOS lane.

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
- The required macOS lane asserts the published base is SIP-disabled; the SIP command remains reserved and absent until
  its deferred child is activated.
- The Linux upstream bug is related provenance/validation evidence, not an implementation blocking edge. Shared helper
  and documentation ownership is sequenced explicitly between implementation children.

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
