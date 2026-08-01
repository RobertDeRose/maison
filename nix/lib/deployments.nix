{
  inputs,
  lib,
  inventoryData,
  systemConfigs,
}:
let
  linuxHosts = lib.filterAttrs (
    _: host: lib.hasSuffix "-linux" host.system && host.deploy.enable
  ) inventoryData.hosts;

  mkNode =
    name: host:
    let
      pkgs = import inputs.nixpkgs { system = host.system; };
      deployRs = import ./deploy-rs.nix { inherit lib pkgs; };
    in
    {
      hostname = host.deploy.hostname;
      sshUser = host.deploy.sshUser;
      remoteBuild = host.deploy.remoteBuild;
      autoRollback = host.deploy.autoRollback;
      magicRollback = host.deploy.magicRollback;

      profiles.system =
        let
          activateSystem = ''
            cd /tmp
            "$PROFILE/bin/activate"
            if ! systemctl is-active --quiet system-manager.target ||
              ! systemctl is-active --quiet maison-runtime-verification.service; then
              echo "Linux runtime verification failed: inspect system-manager.target and maison-runtime-verification.service" >&2
              exit 1
            fi
          '';
        in
        {
          user = "root";
          profilePath = "/nix/var/nix/profiles/system-manager-profiles/system-manager";
          path = deployRs.mkActivation {
            base = systemConfigs.${name};
            activate = activateSystem;
            boot = activateSystem;
          };
        };
    };
in
{
  nodes = lib.mapAttrs mkNode linuxHosts;
}
