{
  base = {
    darwinModules = [ ../profiles/base/darwin.nix ];
    linuxModules = [ ../profiles/base/linux.nix ];
  };

  dev = {
    darwinModules = [ ];
    linuxModules = [ ];
  };

  mac = {
    darwinModules = [ ../profiles/mac/system.nix ];
    linuxModules = [ ];
  };

  linux = {
    darwinModules = [ ];
    linuxModules = [ ../profiles/linux/system.nix ];
  };
}
