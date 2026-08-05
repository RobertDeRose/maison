{
  lib,
  inputs,
}:
let
  validation = import ./validation.nix { inherit lib; };
  profiles = import ./profiles.nix;
  modules = {
    darwin = {
      default = ../modules/darwin/default.nix;
      config = ../modules/darwin/config.nix;
      fonts = ../modules/darwin/fonts.nix;
      homebrewSystem = ../modules/darwin/homebrew-system.nix;
      system = ../modules/darwin/system.nix;
      base = ../profiles/base/darwin.nix;
      mac = ../profiles/mac/system.nix;
    };
    systemManager = {
      default = ../modules/linux/default.nix;
      system = ../modules/linux/system.nix;
      base = ../profiles/base/linux.nix;
      linux = ../profiles/linux/system.nix;
    };
  };
in
{
  inherit
    modules
    profiles
    ;

  inherit (validation)
    compatibleProfile
    profileNames
    supportedSystems
    validDeployRepoPath
    validGithub
    validHostname
    validRemoteHostname
    validSshUsername
    validUsername
    ;

  schema = builtins.fromTOML (builtins.readFile ../../schemas/inventory.toml);

  validateInventory = inventory: import ./inventory.nix { inherit lib inventory; };

  mkDarwinSystem =
    {
      host,
      hostRoot,
      profileRegistry ? profiles,
      inputs,
    }:
    import ./mk-darwin-host.nix {
      inherit
        host
        hostRoot
        inputs
        lib
        profileRegistry
        ;
    };

  mkSystemManagerSystem =
    {
      host,
      hostRoot,
      profileRegistry ? profiles,
      inputs,
    }:
    import ./mk-linux-host.nix {
      inherit
        host
        hostRoot
        inputs
        lib
        profileRegistry
        ;
    };

  mkDeployments =
    {
      inventoryData,
      systemConfigs,
      inputs,
    }:
    import ./deployments.nix {
      inherit
        inputs
        inventoryData
        lib
        systemConfigs
        ;
    };
}
