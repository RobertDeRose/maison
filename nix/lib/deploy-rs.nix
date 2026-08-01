{
  lib,
  pkgs,
}:
let
  # Keep the deploy CLI, remote activation binary, and schema tied to the
  # deploy-rs package selected by the pinned nixpkgs input. Importing the
  # upstream deploy-rs flake would create a second revision and currently
  # emits deprecated string-escape warnings under Lix.
  deployPackage = pkgs.deploy-rs;
  deploySource =
    if deployPackage ? src then
      deployPackage.src
    else
      throw "nixpkgs deploy-rs package does not expose its source for schema validation";

  mkActivation =
    {
      base,
      activate,
      dryActivate ? ''
        test -x "$PROFILE/bin/activate"
        printf '%s\n' "Dry activation validated for $PROFILE"
      '',
      boot ? activate,
    }:
    let
      activationScript = pkgs.writeShellScript "deploy-rs-activate-${base.name}" ''
        set -euo pipefail

        if [[ "''${DRY_ACTIVATE:-0}" == "1" ]]; then
          ${dryActivate}
        elif [[ "''${BOOT:-0}" == "1" ]]; then
          ${boot}
        else
          ${activate}
        fi
      '';
    in
    pkgs.symlinkJoin {
      name = "activatable-${base.name}";
      paths = [ base ];
      postBuild = ''
        ln -s ${activationScript} "$out/deploy-rs-activate"
        ln -s ${deployPackage}/bin/activate "$out/activate-rs"
      '';
    };

  deployChecks =
    deploy:
    let
      profiles = builtins.concatLists (
        lib.mapAttrsToList (
          nodeName: node:
          lib.mapAttrsToList (profileName: profile: {
            path = toString profile.path;
            inherit nodeName profileName;
          }) node.profiles
        ) deploy.nodes
      );
      activationChecks = lib.concatMapStringsSep "\n" (
        profile:
        let
          label = "#${profile.nodeName}.${profile.profileName}";
          activationPath = lib.escapeShellArg "${profile.path}/deploy-rs-activate";
          binaryPath = lib.escapeShellArg "${profile.path}/activate-rs";
        in
        ''
          if [ ! -f ${activationPath} ]; then
            printf '%s is missing deploy-rs-activate\n' ${lib.escapeShellArg label} >&2
            exit 1
          fi
          if [ ! -f ${binaryPath} ]; then
            printf '%s is missing activate-rs\n' ${lib.escapeShellArg label} >&2
            exit 1
          fi
          PROFILE=${lib.escapeShellArg profile.path} DRY_ACTIVATE=1 ${activationPath}
        ''
      ) profiles;
    in
    {
      deploy-schema = pkgs.runCommand "deploy-schema" { } ''
        ${pkgs.check-jsonschema}/bin/check-jsonschema \
          --schemafile ${deploySource}/interface.json \
          ${pkgs.writeText "deploy.json" (builtins.toJSON deploy)}
        touch "$out"
      '';

      deploy-activate = pkgs.runCommand "deploy-activate" { } ''
        ${activationChecks}
        touch "$out"
      '';
    };
in
{
  inherit deployChecks deployPackage mkActivation;
}
