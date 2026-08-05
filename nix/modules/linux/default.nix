# Public system-manager entrypoint. Consumer repositories provide `user`
# and `host` through module arguments and own the surrounding topology.
{ ... }:
{
  imports = [ ./system.nix ];
}
