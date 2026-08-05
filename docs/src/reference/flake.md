# Public flake reference

Maison is a provider-neutral flake. A consumer pins Maison as an input and keeps its own inventory, host topology,
configuration, deployment state, and lock file. Maison's `flake.lock` contains only inputs needed to develop, validate,
and release Maison itself.

## Run the CLI

The packaged CLI does not require a Maison checkout:

```bash
nix run github:RobertDeRose/maison#maison -- --help
```

The same package is available as `inputs.maison.packages.${system}.maison`, and the app is available as
`inputs.maison.apps.${system}.maison`.

## Public outputs

| Output                     | Contract                                                                                  |
|----------------------------|-------------------------------------------------------------------------------------------|
| `packages.<system>.maison` | Store-backed Maison CLI package                                                           |
| `apps.<system>.maison`     | Runnable app wrapper for the CLI package                                                  |
| `darwinModules`            | Reusable nix-darwin modules, including `default`, `base`, `config`, `fonts`, and `system` |
| `systemManagerModules`     | Reusable system-manager modules, including `default` and `system`                         |
| `lib`                      | Maison orchestration functions and inventory validation helpers                           |
| `orchestration`            | Alias for the Maison orchestration library                                                |
| `schemas.inventory`        | Public inventory schema path                                                              |
| `schemas.fnox`             | Provider-neutral fnox contract schema                                                     |
| `fixtures.inventory`       | Neutral valid and invalid inventory fixture corpus                                        |
| `fixtures.fnox`            | Credential-free fnox contract fixture corpus                                              |

The `lib` output also appears under `lib.maison` for consumers that prefer a named namespace. Its stable helpers are:

- `validateInventory inventory` — normalize and validate a consumer inventory;
- `mkDarwinSystem` — compose a consumer-owned nix-darwin host;
- `mkSystemManagerSystem` — compose a consumer-owned system-manager host;
- `mkDeployments` — compose deployment definitions from consumer-owned data;
- `profiles` and the validation predicates — shared framework contracts;
- `validateFnox config` — validate logical fnox metadata without resolving secret values.

The host composition helpers receive consumer inputs, a consumer host record, and the consumer host-root path. Maison
never supplies a personal user, host, deployment target, provider credential, or topology through these outputs.

## Modules

A consumer selects modules in its own flake and supplies its own special arguments:

```nix
{
  inputs,
  ...
}:
{
  darwinConfigurations.example = inputs.darwin.lib.darwinSystem {
    system = "aarch64-darwin";
    specialArgs = {
      user = {
        username = "operator";
        fullName = "Example Operator";
      };
      host = {
        features.personalCache = false;
      };
    };
    modules = [ inputs.maison.darwinModules.default ];
  };
}
```

System-manager consumers use `inputs.maison.systemManagerModules.default` in the same way. The module paths are
framework building blocks; consumer repositories own the composition and all identity-bearing values.

## Checks and fixtures

Run the public contract and platform checks without changing Maison's lock file:

```bash
nix flake check github:RobertDeRose/maison --no-update-lock-file
```

Each supported system exposes `checks.<system>.public` for the packaged CLI, module paths, schemas, and fixture corpora;
the remaining checks cover inventory and platform-specific framework behavior.

The neutral inventory and fnox fixture corpora are intentionally credential-free. Consumers and CI can reuse them to
verify framework handling without requiring an owner account or a particular provider.
