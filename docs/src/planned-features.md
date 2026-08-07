# Planned features

This page is the human-readable roadmap. Beads is authoritative for live status, dependencies, claims, and ready-work
selection.

## Project direction

- Purpose: Maison is a two-layer macOS and Linux configuration system that uses Nix/Lix for privileged system state and mise for user tools, packages, applications, preferences, and dotfiles.
- Current scope: Maison manages Apple Silicon macOS, aarch64 Linux, and x86&#95;64 Linux host configuration; local system activation; remote Linux deployment; user-environment convergence; inventory validation; package/tool/app authoring commands; recovery; and project documentation.
- Boundaries: Maison does not support Intel macOS, Home Manager, arbitrary unmanaged package ownership, strict offline byte-for-byte reproduction, or storing private infrastructure identity and trusted access material in the public control plane.

## Roadmap conventions

- Directory names use `<slug>`.
- Detailed intent belongs in each feature's `design.md`.
- Each feature is one Beads epic/molecule; lifecycle and implementation work are tasks beneath it.
- Human workflow references use `<slug>` or the feature name. Root hashes are retained only for audit.
- Live execution state is queried through Beads.
- Completed features move into [Implemented features](features/index.md).

## Feature map

| Slug                                              | Feature                                                   | Beads root        | Roadmap state | Dependencies                                    | Design                                                                      |
|---------------------------------------------------|-----------------------------------------------------------|-------------------|---------------|-------------------------------------------------|-----------------------------------------------------------------------------|
| `maison-001-root-owned-deployment-transactions`   | MAISON-001: Root-owned deployment transaction state       | `maison-mol-6y0`  | Delivered     | None                                            | [record](features/maison-001-root-owned-deployment-transactions/index.md)   |
| `maison-002-revision-bound-commit-rollback`       | MAISON-002: Revision-bound commit and rollback            | `maison-mol-quq`  | Delivered     | `maison-001-root-owned-deployment-transactions` | [record](features/maison-002-revision-bound-commit-rollback/index.md)       |
| `maison-003-restricted-deployment-privilege`      | MAISON-003: Restricted deployment privilege model         | `maison-mol-4v3`  | Delivered     | `maison-002-revision-bound-commit-rollback`     | [record](features/maison-003-restricted-deployment-privilege/index.md)      |
| `maison-004-private-overlay-configuration`        | MAISON-004: Private configuration split (superseded)      | `maison-mol-e9t`  | Retired       | `maison-003-restricted-deployment-privilege`    | [record](features/maison-004-private-overlay-configuration/index.md)        |
| `maison-005-verified-bootstrap-artifacts`         | MAISON-005: Verified bootstrap artifacts                  | `maison-mol-pa6`  | Delivered     | `maison-004-private-overlay-configuration`      | [record](features/maison-005-verified-bootstrap-artifacts/index.md)         |
| `maison-006-review-gated-dependency-updates`      | MAISON-006: Review-gated dependency updates               | `maison-mol-aqu`  | Delivered     | `maison-005-verified-bootstrap-artifacts`       | [record](features/maison-006-review-gated-dependency-updates/index.md)      |
| `maison-007-parser-backed-toml-mutations`         | MAISON-007: Parser-backed TOML mutations                  | `maison-mol-ywg`  | Delivered     | `maison-006-review-gated-dependency-updates`    | [record](features/maison-007-parser-backed-toml-mutations/index.md)         |
| `maison-008-repository-mutation-locking`          | MAISON-008: Repository mutation locking and journals      | `maison-mol-4ev`  | Delivered     | `maison-007-parser-backed-toml-mutations`       | [record](features/maison-008-repository-mutation-locking/index.md)          |
| `maison-009-authoring-checkout-guard`             | MAISON-009: Authoring checkout guard                      | `maison-mol-74l`  | Delivered     | `maison-008-repository-mutation-locking`        | [record](features/maison-009-authoring-checkout-guard/index.md)             |
| `maison-010-shared-inventory-schema`              | MAISON-010: Shared inventory schema validation            | `maison-mol-bvr`  | Delivered     | `maison-009-authoring-checkout-guard`           | [record](features/maison-010-shared-inventory-schema/index.md)              |
| `maison-011-deterministic-test-suite`             | MAISON-011: Bounded deterministic test suite              | `maison-mol-8mr`  | Delivered     | `maison-010-shared-inventory-schema`            | [record](features/maison-011-deterministic-test-suite/index.md)             |
| `maison-012-plan-apply-parity`                    | MAISON-012: Plan/apply semantic parity                    | `maison-mol-6w9`  | Delivered     | `maison-011-deterministic-test-suite`           | [record](features/maison-012-plan-apply-parity/index.md)                    |
| `maison-013-dotfile-backup-manifests`             | MAISON-013: Exact dotfile backup manifests                | `maison-mol-h8e`  | Delivered     | `maison-012-plan-apply-parity`                  | [record](features/maison-013-dotfile-backup-manifests/index.md)             |
| `maison-014-remote-convergence-restoration`       | MAISON-014: Remote convergence restoration                | `maison-mol-vhhy` | Delivered     | `maison-013-dotfile-backup-manifests`           | [record](features/maison-014-remote-convergence-restoration/index.md)       |
| `maison-015-linux-runtime-verification`           | MAISON-015: Linux runtime activation verification         | `maison-mol-cg3x` | Delivered     | `maison-014-remote-convergence-restoration`     | [record](features/maison-015-linux-runtime-verification/index.md)           |
| `maison-016-pi-typescript-validation`             | MAISON-016: Pi TypeScript validation boundary             | `maison-mol-fmud` | Delivered     | `maison-015-linux-runtime-verification`         | [record](features/maison-016-pi-typescript-validation/index.md)             |
| `maison-017-maison-terroir-repository-split`      | MAISON-017: Maison/Terroir repository split               | `maison-mol-jfhs` | Delivered     | `maison-016-pi-typescript-validation`           | [record](features/maison-017-maison-terroir-repository-split/index.md)      |
| `maison-overlay-copier-bootstrap`                 | Copier fresh consumer bootstrap                           | `maison-mol-5s9`  | Delivered     | `maison-017-maison-terroir-repository-split`    | [record](features/maison-overlay-copier-bootstrap/index.md)                 |
| `maison-overlay-authoring-lifecycle`              | Retired alternate repository command surface              | `maison-mol-3jb`  | Retired       | `maison-overlay-copier-bootstrap`               | [record](features/maison-overlay-authoring-lifecycle/index.md)              |
| `maison-018-cross-platform-bootstrap-integration` | MAISON-018: Cross-platform consumer bootstrap integration | `maison-mol-90l`  | Delivered     | `maison-017-maison-terroir-repository-split`    | [record](features/maison-018-cross-platform-bootstrap-integration/index.md) |

The alternate repository command surface remains retired. The supported architecture is the public Maison framework
plus one selected consumer repository; the retained Copier starter is setup-time only, and consumer Git history is managed
explicitly with Git.

## Later P2 maintainability follow-ups

The review also identified lower-priority maintainability and contract corrections. They remain source material for
future planning after MAISON-001 through MAISON-016 are reconciled: update command help and rollback guarantees,
user-finalization failures, centralized SSH policy, application-backup concurrency, non-TTY logging races, safer
`system clean`, contradictory macOS defaults, shared repository helpers, expanded `doctor`/`user status`, and
shebang-specific shell validation.
