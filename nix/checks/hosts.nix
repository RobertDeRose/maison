{
  lib,
  system,
  inventoryData,
  darwinConfigurations,
  systemConfigs,
}:
let
  hostsForSystem = lib.filterAttrs (_: host: host.system == system) inventoryData.hosts;
  checksForHost =
    name: host:
    if lib.hasSuffix "-darwin" host.system then
      [
        {
          name = "host-${name}-darwin";
          value = darwinConfigurations.${name}.system;
        }
      ]
    else
      [
        {
          name = "host-${name}-system";
          value = systemConfigs.${name};
        }
      ];
in
builtins.listToAttrs (lib.concatLists (lib.mapAttrsToList checksForHost hostsForSystem))
