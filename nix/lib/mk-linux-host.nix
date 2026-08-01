{
  inputs,
  lib,
  profileRegistry,
  host,
  hostRoot,
}:
let
  user = host.user;
  selectedProfiles = map (name: profileRegistry.${name}) host.profiles;
  linuxModules = lib.concatMap (profile: profile.linuxModules) selectedProfiles;
  hostDir = hostRoot + "/${host.name}";
  systemOverride = hostDir + "/system.nix";
  specialArgs = {
    inherit
      inputs
      host
      user
      ;
  };
in
inputs.system-manager.lib.makeSystemConfig {
  # Keep upstream Rust checks enabled. If a future upstream revision breaks
  # under Nix, pin or report that revision rather than globally overriding
  # rustPlatform.buildRustPackage and silently disabling every host's tests.
  modules = [
    {
      nixpkgs.hostPlatform = host.system;
      _module.args = specialArgs;
    }
  ]
  ++ linuxModules
  ++ lib.optional (builtins.pathExists systemOverride) systemOverride;
}
