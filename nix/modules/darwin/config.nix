# nix/modules/darwin/config.nix
# nix-darwin-specific Nix daemon settings: caches, GC, trusted users, and Lix.
{
  pkgs,
  user,
  host,
  ...
}:
let
  cache = import ../common/cache.nix {
    personal = host.features.personalCache;
  };
in
{
  nixpkgs.config.allowUnfree = true;

  nix = {
    package = pkgs.lixPackageSets.latest.lix;
    channel.enable = false;
    optimise.automatic = true;

    settings = {
      builders-use-substitutes = true;
      fallback = cache.fallback;
      experimental-features = [
        "nix-command"
        "flakes"
      ];
      trusted-users = [ user.username ];
      extra-substituters = cache.substituters;
      extra-trusted-public-keys = cache.trustedPublicKeys;
    };

    gc = {
      automatic = true;
      options = "--delete-older-than 7d";
    };
  };
}
