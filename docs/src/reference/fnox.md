# fnox reference

Maison provides a provider-neutral boundary for consumer-owned confidential values. A consumer may choose any fnox
provider; Maison validates only logical names and the runtime safety policy. Maison does not select or authenticate an
age, Bitwarden, cloud, keychain, or other provider.

## Consumer contract

Place a consumer-owned `fnox.toml` at the repository root when runtime secrets are needed:

```toml
root = true
if_missing = "error"
env = "exec"

[providers.consumer_store]
type = "consumer-selected-provider"
endpoint = "https://secrets.example.invalid"

[secrets.GITHUB_TOKEN]
provider = "consumer_store"
key = "source-controlled-logical-reference"
env = "exec"
if_missing = "error"
```

The contract requires:

- `root = true`, so parent and global project configuration cannot silently change the consumer contract;
- `if_missing = "error"`, so required values fail before a Maison mutation starts;
- `env = "exec"`, so values are not injected into an ambient interactive shell;
- provider names and provider `type` values remain opaque and consumer-selected;
- secret names are shell-compatible logical names, while `provider` and `key` are references, not credential values; and
- inline defaults, provider credentials, and private-key fields are rejected by Maison's validator.

`fnox.local.toml` may hold owner-local overrides, but it must be owner-only (`0600` or stricter). Keep it out of Git.
The tracked `fnox.toml` should contain only provider metadata, encrypted material supported by fnox, and logical
references.

Maison publishes the contract as `inputs.maison.schemas.fnox`, neutral fixtures as `inputs.maison.fixtures.fnox`, and
pure evaluation-time validation as `inputs.maison.lib.validateFnox`. The validator returns logical metadata only; it
never returns a secret value for use in a derivation.

## Runtime preflight

When `fnox.toml` exists, Maison validates it and runs the equivalent of:

```bash
FNOX_IF_MISSING=error FNOX_SHELL_OUTPUT=none fnox -c "$CONSUMER_ROOT/fnox.toml" check
```

This read-only preflight runs before plan, apply, update, deployment, and recovery. A failed check stops the operation
before repository, system, or user mutation and reports the logical names that need resolution without printing their
values. Install `fnox` through the consumer's toolchain; Maison does not install or configure a provider on the
consumer's behalf.

Before invoking fnox, Maison copies the declarative configuration into a temporary owner-only directory (`0700`) and
uses owner-only files (`0600`); the directory is removed after the command. Provider credentials and private keys are
fetched only by fnox during this runtime preflight or an activation command. They are passed through
memory/environment boundaries, never command arguments or logs, and never embedded in Nix expressions, derivations, or
the Nix store.
