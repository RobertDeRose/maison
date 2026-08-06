# Design — MAISON-018: Cross-platform consumer bootstrap integration

## Metadata

- Beads feature root: `maison-mol-90l`
- Feature slug: `maison-018-cross-platform-bootstrap-integration`
- Design path: `docs/src/features/maison-018-cross-platform-bootstrap-integration/design.md`
- Implemented record: `docs/src/features/maison-018-cross-platform-bootstrap-integration/index.md`
- Base branch: `main`
- Status: ready for specification review
- Skill version evidence: `Skill version evidence: schema=dstack.skill-version.v1 skill=plan-features installed=0.8.4 canonical=unavailable status=unavailable installed_source=/Users/DeRoseR/.agents/skills/plan-features/SKILL.md checked_at=2026-08-06T15:14:37.416467Z`

## Feature Summary

Provide explicit consumer bootstrap integration tasks for both supported execution environments: Linux in an Apple
Container and macOS in a disposable Lume virtual machine. Rename the existing Linux task to make its platform
boundary explicit, use Trycua's published Tahoe image rather than maintaining a Maison VM image, and record a
future SIP-enabled macOS lane without making it part of the required delivery. The implementation also includes a
Mise-only task that installs a pinned Lume release when the macOS lane needs it; those test tasks are hidden from the
`maison` CLI wrapper.

## User Intent

The user wants the existing `test:bootstrap` command renamed to `test:bootstrap:linux`, wants a new
`test:bootstrap:mac` command, and wants an SIP-enabled lane tracked as deferred work inside the same feature epic.
The macOS test must exercise the real bootstrap path without changing the current Mac host. A prebuilt Trycua Lume
image is preferred over creating or maintaining a Maison-owned image. Lume installation belongs to an explicit Mise
test-task dependency, not to the public `maison` command surface.

## Goals

- Expose `test:bootstrap:linux` for the existing disposable Apple Container bootstrap test.
- Expose `test:bootstrap:mac` for full bootstrap validation in a disposable Apple Silicon macOS VM.
- Use the pinned Maison revision from the consumer lock for both lanes.
- Use the published, versioned `macos-tahoe-cua:26.5.2` Trycua image through Lume for the macOS lane.
- Keep consumer staging, credentials, SSH, VM/container lifecycle, and cleanup owned by the Maison test harness.
- Make successful and interrupted runs unable to modify the production host, production inventory, or private source.
- Track an SIP-enabled macOS lane as an explicitly deferred child task that does not block the required lanes or epic.

## Non-Goals

- Building or publishing a Maison-owned macOS VM image.
- Running Darwin activation against the current macOS host, even under a temporary host account.
- Copying Maison implementation, schemas, private Git objects, credentials, private keys, or a duplicate product test suite into a consumer.
- Changing Maison's core bootstrap or public CLI command semantics beyond adding hidden test-task support.
- Making the SIP-enabled lane a prerequisite for the first macOS lane or for feature close-out.
- Resolving an upstream Linux `system-manager` permission failure discovered while executing the consumer lane; record it as a Maison upstream dependency if it remains.

## User-Facing Behavior

The supported commands are:

```bash
mise run test:bootstrap:linux
mise run test:bootstrap:mac
```

The existing `test:deploy` command remains a Linux deployment integration test and is not renamed. These test tasks
are invoked directly through Mise; they are intentionally absent from the `maison` wrapper's public command surface.
A future, deferred command is reserved as:

```bash
mise run test:bootstrap:mac-sip
```

The deferred command is not required to run or pass before the feature's required implementation can be delivered.

## Requirements

### Functional Requirements

1. Maison provides hidden Mise tasks for `test:bootstrap:linux`, `test:bootstrap:mac`, and the deferred
   `test:bootstrap:mac-sip`; these tasks are available through `mise run` but are not resolvable through the `maison`
   CLI wrapper.
2. A hidden macOS test dependency installs a pinned, checksum-verified Lume release when `lume` is absent, verifies
   the resulting executable/version, and leaves installation under the host user's control. It is not run by public
   bootstrap, apply, deploy, or other Maison CLI commands.
3. The Linux task file and all reader-facing references use `test:bootstrap:linux`; no supported documentation claims
   that the unqualified `test:bootstrap` command exists.
4. The Linux task retains the current pinned Maison bootstrap behavior, staged consumer fixture, token handling,
   disposable Apple Container lifecycle, convergence assertions, and interruption cleanup.
5. The macOS task requires Lume on Apple Silicon, uses the versioned Trycua image `macos-tahoe-cua:26.5.2`, and
   clones a uniquely named worker from a stopped base VM for each run.
6. The macOS task runs headlessly through Lume's VM/SSH interface, stages a disposable consumer with a temporary
   `aarch64-darwin` host and test user, and invokes the public Maison bootstrap script at the full locked revision.
7. The macOS task verifies the Maison checkout revision, Nix-Darwin/system convergence, mise/fnox/Maison user
   convergence, UTF-8 locale state, and the expected disposable host identity.
8. Both required lanes delete or stop their disposable resources and remove staging/token material on success,
   failure, and interruption.
9. The future SIP lane is represented as a deferred Beads child with an acceptance contract for the same bootstrap
   assertions under SIP-enabled guest state; it has no blocking edge into the required Linux or macOS lane.

### Quality Requirements

- Never pipe an unreviewed or floating bootstrap script into a shell; download the exact locked Maison revision to a
  file and validate it before execution.
- Never mount or copy a host private SSH key; only a public key may enter a disposable guest when SSH setup requires it.
- Keep GitHub tokens out of repositories, command-line arguments, logs, and committed test artifacts.
- Avoid read-write mounts of the current repository; transfer only a deterministic disposable stage.
- Validate VM/image identity, host names, addresses, and paths before interpolation into inventory or remote commands.
- Use versioned image and VM names, never `latest`, for reproducible evidence.

### Compatibility and Migration Requirements

- Existing Linux users must replace `mise run test:bootstrap` with `mise run test:bootstrap:linux`.
- Existing `mise run test:deploy` behavior remains unchanged except for shared helper refactoring required by the
  platform-specific bootstrap tasks.
- The public documentation must explain that the macOS image is a published Trycua base with known preconditions,
  including its SIP state, rather than a Maison-built pristine image.

## Existing Context

Maison currently has deterministic repository tests and the consumer/bootstrap/runtime task surfaces, but no
platform-specific consumer integration task group. The restored Linux integration implementation exists in the
unpublished Terroir worktree and is being moved into Maison so the reusable harness, Lume lifecycle, and hidden Mise
tasks have one owner. The consumer remains an external input selected through `MAISON_CONSUMER_ROOT`; Maison must not
copy the consumer's private Git history or make Terroir a required checkout for its normal test suite.

Maison owns the bootstrap script, runtime tasks, schemas, reusable orchestration, platform test harness, and test-task
installation dependencies. A consumer owns its inventory, host modules, and configuration. The current production
macOS host must never be used as the test target.

Lume provides local Apple Virtualization.framework VMs on Apple Silicon. Trycua documents the public versioned image
`macos-tahoe-cua:26.5.2`, which supplies a Tahoe guest with Command Line Tools, SSH, and unattended login setup.
That base has SIP disabled; this is recorded as a precondition for the required lane and is not silently presented as
SIP-on coverage.

## Proposed Design

### Hidden Mise task surface

Add test tasks under Maison's `.mise/tasks/test/` tree and update `bin/maison` so `test:*` tasks are excluded from its
public command resolver and help output. They remain directly invocable with `mise -C "$MAISON_HOME" run ...`.

### Lume installation dependency

Add a hidden Mise task that is a dependency of `test:bootstrap:mac`. It downloads the pinned Lume release artifact,
verifies its checksum (and release signature when supplied by the upstream release), installs it for the host user,
and verifies `lume --version`. It must be idempotent and must never be pulled into the ordinary `maison` CLI workflow.
Document the explicit host-side effect and recovery path. The task may then pull/reuse the versioned Trycua Tahoe base
VM, but each test run clones and deletes a worker.

### Linux lane

Rename the task file to `.mise/tasks/test/bootstrap/linux` (or the repository's equivalent Mise nested-task path)
and update task metadata, contract checks, docs, and any Beads acceptance text. Preserve the existing Linux Apple
Container implementation and keep its image helper Linux-only.

### macOS lane

Add a platform-specific task and a small Lume helper layer. The task will:

1. Parse the Maison revision from `flake.lock` without resolving a mutable branch.
2. Require `lume`, `jq`, `ssh`, `scp`, and the existing staging prerequisites.
3. Require or pull the exact Trycua base image `macos-tahoe-cua:26.5.2` into a host-local named base VM; never mutate
   that base during a test.
4. Clone the stopped base into a unique worker and boot it without a display.
5. Obtain the worker address from Lume, install only the host public SSH key into the disposable guest, and use
   noninteractive SSH/SCP for stage transfer and commands.
6. Copy a deterministic staged consumer into the guest. The stage adds only a test user and a temporary Darwin host,
   and uses no production host record or private endpoint.
7. Download the pinned public Maison `bootstrap.sh` into the guest, verify its expected content/checksum contract, and
   run it with `--consumer`, `--host`, `--repo`, and the full locked `--ref`.
8. Run verification in the guest and write only sanitized result output to the host log.
9. Shut down/stop and delete the worker, remove host-side staging and token files, and clean up on signals.

The test may use the published image's disposable `lume` account rather than creating a host account. If bootstrap
needs privileged noninteractive execution, privilege setup must be confined to the disposable guest and removed with
the worker; no host sudoers or account changes are permitted. Lume itself may be installed on the host only by the
explicit hidden Mise dependency described above.

### SIP lane

Reserve `test:bootstrap:mac-sip` as a deferred child. It will use a SIP-enabled disposable macOS worker and repeat
the required macOS assertions. Its guest source/preparation may be selected when the task is activated, but the
required feature lanes do not depend on it and the first macOS lane must explicitly report that it is SIP-disabled.

## Architecture Consistency

### Existing Patterns Reused

- Maison remains the owner of bootstrap, validation, flake modules, and activation orchestration.
- The transferred deterministic stage, full-lock revision resolution, token-file, and signal-cleanup patterns are
  reused.
- Disposable named resources are created outside the production inventory and verified before assertion.
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
- SIP-enabled coverage is deferred and does not block the first macOS lane.

### Architecture Documentation Changes

Update Maison's operations and task-reference documentation to define the hidden integration-task boundary and the
consumer input contract. No new architecture page is required.

## Operational Considerations

The macOS lane is local Apple Silicon infrastructure and can install Lume through its explicit hidden Mise
prerequisite. It requires sufficient host disk/memory and a versioned Trycua image. The base VM is host-local test
infrastructure and must remain stopped and unmodified. Each worker is single-use and must be deleted even after failed
bootstrap. Lume telemetry should be disabled for privacy-sensitive runs. Standard CI runners are not assumed to
support nested macOS virtualization.

## Documentation Impact

| Documentation concern      | Exact page                                                                   | Create or update | Planned change                                                                                                 | Owning Beads task                    |
|----------------------------|------------------------------------------------------------------------------|------------------|----------------------------------------------------------------------------------------------------------------|--------------------------------------|
| Usage / Operations         | `docs/src/operations.md`                                                     | Update           | Document hidden integration tasks, Lume installation side effects, image preconditions, cleanup, and SIP lane. | `maison-mol-4pv.1`, `.2`, `.3`, `.4` |
| Development                | `docs/src/development/tooling.md`                                            | Update           | Document direct Mise invocation and host prerequisites.                                                        | `maison-mol-4pv.1`                   |
| Reference                  | `docs/src/task-reference.md`                                                 | Update           | Define task names, hidden CLI boundary, arguments, image/version contracts, and states.                        | `maison-mol-4pv.1`, `.2`, `.3`, `.4` |
| Reference                  | `docs/src/reference/tooling.md`                                              | Update           | Add test-task dependency and validation contracts.                                                             | `maison-mol-4pv.1`, `.2`, `.3`       |
| Navigation                 | `docs/src/SUMMARY.md`                                                        | Update           | Register the feature design.                                                                                   | `maison-mol-o5z`                     |
| Planned Features           | `docs/src/planned-features.md`                                               | Update           | Add MAISON-018 roadmap entry and dependency status.                                                            | `maison-mol-o5z`                     |
| Implemented Feature Record | `docs/src/features/maison-018-cross-platform-bootstrap-integration/index.md` | Create close-out | Record delivery, deferred SIP lane, and evidence.                                                              | `maison-mol-55k`                     |

## Validation Strategy

- Run the task contract/static checks for all hidden task names and verify they are absent from `maison help` and
  `maison tasks`.
- Run the Lume installer task in a disposable host/tooling environment and verify idempotent version/checksum behavior.
- Run `bash -n`, ShellCheck, and shfmt on all new/changed shell files.
- Run `mise run consumer:validate`, `python3 scripts/check-docs.py`, `mise run check`, and `git diff --check`.
- In a prepared Apple Container environment, run `mise run test:bootstrap:linux` and record any upstream
  system-manager blocker if it remains unresolved.
- In a prepared Apple Silicon host, run `mise run test:bootstrap:mac` and inspect
  worker deletion after both success and injected failure/interruption paths.
- Verify logs and staged artifacts contain no token, private key, private endpoint, or host repository path.
- Do not run the deferred SIP lane during required feature validation.

## Implementation Decomposition

1. Add the hidden Mise task surface and verified Lume installation dependency (`maison-mol-4pv.1`).
2. Move/reconcile the Linux bootstrap and deployment harness under Maison (`maison-mol-4pv.2`).
3. Add the Lume macOS bootstrap task and shared platform-safe staging/VM helpers (`maison-mol-4pv.3`).
4. Reserve the SIP-enabled lane as an explicitly deferred task with no dependency into required delivery
   (`maison-mol-4pv.4`).

## Dependencies and Parallelism

The Linux child may retain a real upstream system-manager dependency if the failure remains after the move. The
macOS child is independent of that Linux blocker but depends on the reviewed feature specification. The Lume installer
and hidden CLI-boundary tasks precede the macOS lane. Shared helper edits must be coordinated so the Linux task is not
broken while the macOS lane is added. The SIP child is deferred and does not block the required children or
implementation coordinator.

## Rollout and Migration

Update local scripts and documentation to call `test:bootstrap:linux`. Do not retain an alias unless a separate
compatibility decision is recorded; the explicit rename is intended to remove platform ambiguity. The macOS task is
opt-in and does not alter production activation or default repository checks.

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
- Using `curl | bash` or a floating Maison branch: it does not provide an auditable bootstrap input.
- Making SIP-enabled coverage a prerequisite: it would delay the useful published-base lane and is explicitly deferred.

## Open Questions

None required for the first implementation lanes.

## Deferred Decisions

- The exact SIP-enabled guest preparation method is owned by the deferred SIP child; it must produce an SIP-enabled
  worker without changing the current host and must not block the required macOS lane.

## Planning Record

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

### Source Material

- The unpublished consumer-side integration implementation being transferred into Maison.
- Maison `bootstrap.sh`, `system:apply`, `bin/maison`, and existing Mise task conventions.
- Maison's consumer contract, test suite, and Darwin profile modules.
- Trycua Lume documentation: `https://cua.ai/docs/how-to-guides/driver/run-in-macos-lume-vm`.
- Trycua Lume CLI documentation: `https://cua.ai/docs/reference/lume/cli-reference`.
