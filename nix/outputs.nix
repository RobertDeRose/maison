{
  inputs,
  inventory,
  inventoryFile,
}:
let
  lib = inputs.nixpkgs.lib;
  inventoryData = import ./lib/inventory.nix {
    inherit lib inventory;
  };
  profileRegistry = import ./lib/profiles.nix;
  hostRoot = builtins.dirOf inventoryFile + "/hosts";

  darwinHosts = lib.filterAttrs (_: host: lib.hasSuffix "-darwin" host.system) inventoryData.hosts;
  linuxHosts = lib.filterAttrs (_: host: lib.hasSuffix "-linux" host.system) inventoryData.hosts;
  deploymentSystems = lib.unique (
    lib.mapAttrsToList (_: host: host.system) (lib.filterAttrs (_: host: host.deploy.enable) linuxHosts)
  );

  darwinConfigurations = lib.mapAttrs (
    _: host:
    import ./lib/mk-darwin-host.nix {
      inherit
        inputs
        lib
        profileRegistry
        host
        hostRoot
        ;
    }
  ) darwinHosts;

  systemConfigs = lib.mapAttrs (
    _: host:
    import ./lib/mk-linux-host.nix {
      inherit
        inputs
        lib
        profileRegistry
        host
        hostRoot
        ;
    }
  ) linuxHosts;

  deploy = import ./lib/deployments.nix {
    inherit
      inputs
      lib
      inventoryData
      systemConfigs
      ;
  };
in
inputs.flake-parts.lib.mkFlake { inherit inputs; } {
  systems = [
    "aarch64-darwin"
    "aarch64-linux"
    "x86_64-linux"
  ];

  flake = {
    inherit
      darwinConfigurations
      systemConfigs
      deploy
      ;
  };

  perSystem =
    { pkgs, system, ... }:
    let
      hasSystemManager = builtins.hasAttr system inputs.system-manager.packages;
      deployRs = import ./lib/deploy-rs.nix { inherit lib pkgs; };
      systemManagerPackage =
        let
          systemManagerPkgs = import inputs.nixpkgs {
            inherit system;
            overlays = [ inputs.system-manager.overlays.default ];
          };
        in
        systemManagerPkgs.system-manager;
      inventoryPackage = pkgs.writeShellApplication {
        name = "maison-inventory";
        runtimeInputs = [ pkgs.python3 ];
        text = ''
          export MAISON_INVENTORY_SCHEMA=${../schemas/inventory.toml}
          exec python3 ${../.mise/lib/inventory.py} "$@"
        '';
      };
      nixfmtPackage = import ./lib/nixfmt-rs.nix {
        inherit
          lib
          pkgs
          system
          ;
      };
    in
    {
      # The contributor environment and `nix fmt` must use one formatter
      # version. Read the mise lock directly so an update advances both.
      formatter = pkgs.nixfmt-tree.override { inherit nixfmtPackage; };

      packages = {
        inherit (pkgs) nh deploy-rs;
        maison-inventory = inventoryPackage;
        nixfmt = nixfmtPackage;
      }
      // lib.optionalAttrs hasSystemManager {
        system-manager = systemManagerPackage;
      };

      apps = {
        deploy = {
          type = "app";
          program = "${pkgs.deploy-rs}/bin/deploy";
        };
        nh = {
          type = "app";
          program = "${pkgs.nh}/bin/nh";
        };
      }
      // lib.optionalAttrs hasSystemManager {
        system-manager = {
          type = "app";
          program = "${systemManagerPackage}/bin/system-manager";
        };
      };

      checks = {
        inventory = import ./checks/inventory.nix {
          inherit pkgs inventoryData;
        };
      }
      // import ./checks/hosts.nix {
        inherit
          lib
          system
          inventoryData
          darwinConfigurations
          systemConfigs
          ;
      }
      // lib.optionalAttrs (lib.elem system deploymentSystems) (deployRs.deployChecks deploy);
    };
}
