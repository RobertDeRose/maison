# Public nix-darwin entrypoint. Consumer repositories provide `user` and
# `host` through specialArgs and compose any additional host modules locally.
{ ... }:
{
  imports = [
    ./config.nix
    ./system.nix
  ];
}
