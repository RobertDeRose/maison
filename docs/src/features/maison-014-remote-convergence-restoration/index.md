# MAISON-014: Remote convergence restoration

## Delivery Summary

- Beads feature root: `maison-mol-vhhy`
- Status: delivered
- Pull request: pending delivery action
- Merge commit: pending delivery action
- Design record: [design.md](design.md)

## Delivered Capability

Maison now restores the repository revision before attempting restricted managed-user recovery when remote user
convergence fails. Recovery repairs reversible user state from the restored repository and records package/app side effects separately instead of implying that external package operations were rolled back.

## User-Facing Behavior

`maison deploy <host>` keeps the original user-convergence failure as its exit status. After a verified repository
rollback, it runs recovery as the managed user from the restored repository. Recovery repairs dotfiles, mise lock links,
non-package mise state, and Maison-owned finalization; it does not rerun package/app convergence, application-backup
migration, legacy Git migration, system activation, or Nix rollback.

Recovery preserves the deployment's explicit `--force-dotfiles` choice and never enables it implicitly. It writes an
atomically replaced, mode-0600 JSON diagnostic at:

```text
~/.local/state/maison/recovery/remote-convergence-<failed-revision>.json
```

The report retains the failed and restored revisions, initial and recovery statuses, completed steps, force state, and
observed package/app side effects. A rollback failure skips recovery and leaves the transaction inspection path for
operator recovery; a separate recovery failure is reported without hiding the original failure.

## Design Integration

The implementation extends the existing Python user-convergence planner with an internal restricted recovery mode and
reuses the existing remote repository transaction and task adapters. The deployment account performs only privileged
rollback and verification; the managed user performs user-owned recovery. Root-owned transaction journals, staging
paths, rollback paths, and locks remain outside managed-user control. Nix/Lix retains system ownership and mise retains
user convergence ownership.

## Operational Impact

Operators should inspect the recovery report after a failed remote deployment and treat package/app entries marked
`started`, `completed`, `failed`, or `unknown` as follow-up work when indicated. Recovery is deliberately limited to
reversible user state and does not promise package-manager rollback. An explicit `--force-dotfiles` deployment choice
is honored consistently across the initial convergence and restricted recovery.

## Reference and Contracts

- [Architecture](../../architecture.md)
- [Remote deployment](../../deployment.md)
- [Recovery](../../recovery.md)
- [Operations](../../operations.md)
- [Task reference](../../task-reference.md)

## Validation Evidence

- `python3 -m unittest -v tests.test_remote_convergence tests.test_user_convergence tests.test_deployment_contracts` — passed (39 tests).
- `python3 scripts/check-docs.py` — passed.
- `uv run scripts/check-docs.py` — passed during close-out.
- `python3 -m py_compile .mise/lib/user_convergence.py tests/test_remote_convergence.py` — passed.
- `shellcheck -x .mise/tasks/deploy .mise/tasks/user/recover` and `shfmt -d --apply-ignore .mise/tasks/deploy .mise/tasks/user/recover scripts/user-prepare.sh` — passed.
- `mise exec -- hk check` — passed.
- `mise run check` — passed (138 tests plus data, shell, and Nix checks).

## Design Reconciliation

### Delivered as Designed

- Added rollback-before-recovery ordering with restored-revision verification.
- Added restricted managed-user recovery for reversible user state only.
- Preserved explicit force-dotfile behavior without implicit force.
- Added atomic private diagnostics with separate package/app side-effect states.
- Added behavioral coverage for sequence, safe-step exclusion, revision boundaries, force forwarding, reports, and failure semantics.

### Intentional Changes

- Recovery uses a compatibility adapter that uploads the current tested recovery helper when the restored repository does
  not contain a compatible recovery task, so recovery behavior does not depend on the failed revision's older source.
- The package/app report may be `unknown` when the initial convergence did not create its event journal; this avoids
  claiming that package convergence was not started when the observed state is incomplete. Recovery-only events do not
  change that classification.
- If the restored user environment has no usable mise command or trust step, the uploaded current helper runs directly
  so the recovery failure still produces the diagnostic report.
- Architecture documentation now states the remote rollback/recovery boundary explicitly.

### Deferred Work

- Package/app operations that already ran remain manual follow-up; this feature does not attempt external rollback.
- Pull-request and merge metadata remain pending the delivery action selected after close-out.

### Rejected or Removed Scope

- No package/app rollback, system activation, Nix rollback, application-backup migration, or legacy Git migration was
  added to restricted recovery.
- No new privileged transaction namespace or parallel operator command surface was introduced.

## Documentation Updated

- `docs/architecture.md`
- `docs/deployment.md`
- `docs/recovery.md`
- `docs/operations.md`
- `docs/task-reference.md`
- `docs/src/features/maison-014-remote-convergence-restoration/design.md`
- `docs/src/features/maison-014-remote-convergence-restoration/index.md`
- `docs/src/features/index.md`
- `docs/src/planned-features.md`
- `docs/src/SUMMARY.md`

## Audit Trail

- Specification reconciliation: `maison-mol-ugkm`, commit `80f33aa1d3318e4cb4513af3cde0ba82f59be8dd`.
- Contract tests: `maison-mol-75xd.1`, commit `25183b23a3642e0468ce6886d1f7e36eb14df552`.
- Implementation: `maison-mol-75xd.2`, commit `0cbb56cdcb78e9093465095b227d0085094acadc`.
- Documentation reconciliation: `maison-mol-xelx`.
- Validation: `maison-mol-6ten`.
- Holistic delivery review: `maison-mol-7dpa`.
- Documentation drift review: `maison-mol-nc5u`.
