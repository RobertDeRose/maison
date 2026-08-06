# MAISON-018: Cross-platform consumer bootstrap integration

## Delivery Summary

- Beads feature root: `maison-mol-90l`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison now owns hidden, direct-Mise integration lanes for consumer bootstrap validation on both supported disposable
platforms:

- `test:bootstrap:linux` runs the committed external consumer in an Apple Container.
- `test:bootstrap:mac` runs the pinned consumer bootstrap in a headless Trycua Tahoe worker through Lume.
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
host capacity. It uses the published `macos-tahoe-cua:26.5.2` base, verifies Tahoe 26.5.2/build `25F84`, Command
Line Tools, SSH/unattended login, and SIP disabled, then clones a disposable worker. SIP-enabled coverage remains
the deferred `maison-mol-4pv.4` child; no `test:bootstrap:mac-sip` task is shipped.

## Design Integration

The implementation preserves the two-layer ownership boundary: Maison owns generic orchestration, schemas, staging,
bootstrap verification, task hiding, and disposable test infrastructure; consumers own inventory, host modules, and
configuration. Stages contain only committed external consumer content with generated temporary topology. GitHub
bootstrap content is fetched at the consumer's full public Maison lock revision and checked against its Git blob ID.

Deployment uses generated ephemeral ed25519 keys, transfers only public keys, and uses `IdentitiesOnly=yes`. Tokens,
keys, downloaded scripts, stages, workers, and containers are removed on every success, failure, and interruption path.
The macOS task records pinned-base provenance before allowing a same-name base to be reused.

## Operational Impact

Integration lanes are opt-in host operations, not public bootstrap/apply/deploy behavior. Linux uses Apple Container;
macOS uses host-local Lume infrastructure and a published Trycua base rather than a Maison-owned image. The base is
never deleted by normal cleanup. The macOS lane's persistent result log, when `MAISON_MAC_LOG` is set, contains only
sanitized summaries; detailed command output remains in owner-only temporary files.

The authenticated macOS lane was attempted twice on the current host but could not complete the large pinned image
pull because of host capacity. No guest or production host was used. This remains external validation evidence in
Beads `maison-fea`, not a hidden pass claim. The known Linux `system-manager` read-only `/nix/store` failure remains
external evidence in `maison-jkh`.

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
- Authenticated macOS integration — unavailable on this host at the pinned image pull; r1/r2 evidence is retained in
  `/tmp/maison-018-mac-run-r1.log` and `/tmp/maison-018-mac-run-r2.log` and tracked by `maison-fea`.
- Linux integration/deployment — the known upstream `system-manager` blocker is tracked by `maison-jkh`.

## Design Reconciliation

### Delivered as Designed

- Added explicit Linux and macOS hidden task names without retaining the ambiguous integration alias.
- Added the pinned Lume dependency and published Trycua Tahoe worker lifecycle.
- Reused shared consumer staging, lock parsing, GitHub blob verification, token, SSH, and cleanup behavior.
- Kept the deferred SIP lane non-blocking and absent from the shipped task surface.

### Intentional Changes

- The macOS lane records owner-only provenance for task-managed pinned bases so a same-name unmanaged VM cannot bypass
  the image contract.
- The macOS task uses the published disposable `lume` account for initial public-key installation, then validates the
  staged test user's user-layer convergence separately.
- Prepared-host integration remains an explicit external limitation rather than a waived or simulated success.

### Deferred Work

- `test:bootstrap:mac-sip` and SIP-enabled worker preparation remain deferred under `maison-mol-4pv.4`.
- A prepared host with enough capacity must complete the pinned Tahoe pull and macOS guest lane; `maison-fea` records
  the required follow-up evidence.
- The Linux `system-manager` integration blocker remains external work under `maison-jkh`.
- Pull-request and merge metadata remain pending the delivery action selected after close-out.

### Rejected or Removed Scope

- No current-host Darwin activation, production inventory use, private SSH state, or Maison-owned macOS image was added.
- No network-piped installer, floating Maison revision, private consumer history, or public `test:*` command surface was
  introduced.

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
- Implementation and child reviews approved the bounded changes. Close-out delivery and drift reviews remain part of
  the current lifecycle.
