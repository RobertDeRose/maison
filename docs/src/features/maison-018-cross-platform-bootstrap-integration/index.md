# MAISON-018: Cross-platform consumer bootstrap integration

## Delivery Summary

- Beads feature root: `maison-mol-90l`
- Status: delivered
- Pull request: not created
- Merge commit: `e6c7cb3a12d9c6c87856256dae53302bbc7729d8` (fast-forward)
- Design record: [design.md](design.md)

## Delivered Capability

Maison now owns hidden, direct-Mise integration lanes for consumer bootstrap validation on both supported disposable
platforms:

- `test:bootstrap:linux` runs the committed external consumer in an Apple Container.
- `test:bootstrap:mac` runs the consumer bootstrap in a headless worker cloned from the supplied local Tahoe VM through Lume.
- `test:lume:install` installs the checksum-verified, user-local Lume 0.5.1 prerequisite.

The public `maison` command surface omits every `test:*` task. Consumer configuration remains external input; Maison
owns staging, immutable bootstrap verification, disposable resource lifecycle, and validation contracts.

## User-Facing Behavior

Run the required lanes directly from the Maison checkout:

```bash
mise -C "$MAISON_HOME" run test:bootstrap:linux -- --consumer "$MAISON_CONSUMER_ROOT"
mise -C "$MAISON_HOME" run test:bootstrap:mac -- --consumer "$MAISON_CONSUMER_ROOT"
mise -C "$MAISON_HOME" run test:deploy -- --consumer "$MAISON_CONSUMER_ROOT"
```

The macOS lane requires Apple Silicon macOS 13 or newer, verified Lume 0.5.1, GitHub authentication, and sufficient
host capacity. It uses the Nix-prepared local `macos-tahoe-with-nix` base by default, or `MAISON_MACOS_BASE_NAME`
for another stopped local copy, verifies macOS 26.6.1/build `25G76`, the installed Nix daemon, SSH/unattended login,
and SIP enabled, then clones a disposable worker. The worker grants passwordless sudo only to its disposable `lume` and
`tester` accounts, creates the disposable test user, and installs Command Line Tools when the supplied image does not
already contain them, before running the pinned bootstrap.
No image is pulled or published by the task.

## Design Integration

The implementation preserves the two-layer ownership boundary: Maison owns generic orchestration, schemas, staging,
bootstrap verification, task hiding, and disposable test infrastructure; consumers own inventory, host modules, and
configuration. Stages contain only committed external consumer content with generated temporary topology. GitHub
bootstrap content is fetched at the consumer's full public Maison lock revision by default and checked against its Git
blob ID. Reviewed branch testing may set `MAISON_MACOS_BOOTSTRAP_REF` (or use the `feat/test-bootstrap-macos`
checkout default); the harness resolves the branch head, verifies its blob, and passes the branch through bootstrap's
`--ref` clone path.

Deployment uses generated ephemeral ed25519 keys, transfers only public keys, and uses `IdentitiesOnly=yes`. Tokens,
keys, downloaded scripts, stages, workers, and containers are removed on every success, failure, and interruption path.
The macOS task validates the supplied local base before cloning it and never deletes the user-owned base.

## Operational Impact

Integration lanes are opt-in host operations, not public bootstrap/apply/deploy behavior. Linux uses Apple Container;
macOS uses host-local Lume infrastructure and the user-supplied local Tahoe base. The base is never deleted by normal
cleanup. The macOS lane's persistent result log, when `MAISON_MAC_LOG` is set, contains only sanitized summaries;
detailed command output remains in owner-only temporary files. Earlier Trycua pull failures remain historical evidence in
Beads `maison-fea`; the task no longer attempts that external pull. The known Linux `system-manager` read-only
`/nix/store` failure remains external evidence in `maison-jkh`.

## Reference and Contracts

- [Operations](../../operations.md)
- [Task reference](../../task-reference.md)
- [Development tooling](../../development/tooling.md)
- [Tooling reference](../../reference/tooling.md)
- [Feature design](design.md)

## Validation Evidence

- `mise run check` — passed, 242 tests; final evidence: `/tmp/maison-018-3-full-check-r2.log`.
- `mise run check:shell` — passed; all 55 task definitions validated with ShellCheck and syntax checks.
- `mise run docs:check` and locked `rumdl` on assigned pages — passed.
- Focused macOS contract tests — passed, 4 tests.
- Focused Linux/bootstrap/Lume contract tests — passed, 19 tests.
- Real pinned Lume 0.5.1 host installation, adjacent app-bundle execution, and default-root lock behavior — passed;
  installation evidence is retained in `/tmp/maison-018-lume-host-reinstall-r3.log`.
- Authenticated macOS integration — pending the local-base run after this contract update; earlier Trycua pull evidence
  is retained in `/tmp/maison-018-mac-run-r1.log`, `/tmp/maison-018-mac-run-r2.log`, and
  `/tmp/maison-fea-mac-run-r3.log`.
- Linux integration/deployment — the known upstream `system-manager` blocker is tracked by `maison-jkh`.

## Design Reconciliation

### Delivered as Designed

- Added explicit Linux and macOS hidden task names without retaining the ambiguous integration alias.
- Added the pinned Lume dependency and local Tahoe worker lifecycle using the supplied Lume base.
- Reused shared consumer staging, lock parsing, GitHub blob verification, token, SSH, and cleanup behavior.
- Kept the deferred SIP lane non-blocking and absent from the shipped task surface.

### Intentional Changes

- The macOS lane validates the supplied local base's version, build, Nix daemon, SSH/unattended-login state, and SIP
  status before cloning it; the user-owned base remains outside task cleanup.
- The macOS task uses the disposable `lume` account for local-base preflight, worker privilege preparation, test-user
  creation, and public-key installation, then validates the staged test user's user-layer convergence separately.
- Prepared-host integration remains an explicit external limitation rather than a waived or simulated success.

### Deferred Work

- `test:bootstrap:mac-sip` remains absent under `maison-mol-4pv.4`; the required local-image lane now exercises a
  SIP-enabled base directly.
- The local-base macOS guest lane must complete and record its bootstrap evidence under `maison-fea`.
- The Linux `system-manager` integration blocker remains external work under `maison-jkh`.
- Original feature delivery completed locally by fast-forwarding `main`; this follow-up updates the macOS validation
  contract in the standalone blocker task and adds an explicit branch-bootstrap testing path.

### Rejected or Removed Scope

- No current-host Darwin activation, production inventory use, private SSH state, or Maison-owned macOS image was added;
  the task consumes the user-owned local Lume base without publishing or deleting it.
- No network-piped installer, unresolved Maison revision, private consumer history, or public `test:*` command
  surface was introduced; branch testing remains an explicit verified harness override.

## Documentation Updated

- `docs/operations.md`
- `docs/task-reference.md`
- `docs/src/development/tooling.md`
- `docs/src/reference/tooling.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`
- `docs/src/features/index.md`
- This implemented record

## Audit Trail

- Specification reconciliation: `8279024`, `09e29b1`.
- Hidden tooling/Lume prerequisite: `e6a82aef5caa680c9c825841d13746ec681d43a2`.
- Linux integration harness: `ec6d51d216d540bfd2267a02bb176a32c7ace790`.
- Lume app-bundle correction: `a7db2169bdfb6027f874fc8d80f8c33f137bbb19`.
- Lume default-root provenance/lock correction and macOS lane: `a6666fec92a5761bce6df89863117ad5abfafec0`,
  `d900b9f64dc26cc514c59452bc1114285e095277`.
- Implementation children `.1`, `.2`, and `.3` are closed; `.4` is explicitly deferred.
- Implementation and child reviews approved the bounded changes. Close-out delivery and drift reviews approved the
  final implementation and documentation boundary.
- Delivery merge: `e6c7cb3a12d9c6c87856256dae53302bbc7729d8` (fast-forward); pull request: not created.
