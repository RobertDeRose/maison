{
  description = "Maison provider-neutral configuration orchestration framework";

  # Flake-level cache configuration must remain literal. Importing these
  # values leaves thunks that newer Nix/Lix releases reject before evaluating
  # outputs. The standard cache is already configured by Nix, while fallback
  # remains an execution preference supplied by repository tasks.
  nixConfig = {
    extra-substituters = [
      "https://nix-community.cachix.org"
      "https://cache.numtide.com"
    ];
    extra-trusted-public-keys = [
      "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
      "niks3.numtide.com-1:DTx8wZduET09hRmMtKdQDxNNthLQETkc/yaX7M4qK0g="
    ];
  };

  inputs = {
    nixpkgs.url = "git+https://github.com/NixOS/nixpkgs?ref=nixpkgs-unstable&shallow=1";

    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };

    darwin = {
      url = "github:nix-darwin/nix-darwin";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nix-homebrew.url = "github:zhaofengli/nix-homebrew";

    nix-hex-box = {
      url = "github:RobertDeRose/nix-hex-box";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.darwin.follows = "darwin";
    };

    system-manager = {
      url = "github:numtide/system-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs:
    let
      # Maison's own flake is a neutral development/release flake. Consumer
      # repositories import the public helpers and own their own inventory.
      inventoryFile = ./inventory.toml;
    in
    import ./nix/outputs.nix {
      inherit inputs inventoryFile;
      inventory = builtins.fromTOML (builtins.readFile inventoryFile);
    };
}
