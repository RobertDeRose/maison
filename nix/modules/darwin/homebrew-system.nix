# Homebrew is retained only for packages whose installers modify OS-level
# state and therefore do not belong to the mise-managed user layer.
{
  user,
  ...
}:
{
  nix-homebrew = {
    enable = true;
    user = user.username;
    autoMigrate = true;
    extraEnv.HOMEBREW_NO_ENV_HINTS = "1";
  };

  homebrew = {
    enable = true;
    onActivation = {
      autoUpdate = false;
      upgrade = false;
      cleanup = "none";
    };

    taps = [
      {
        name = "macos-fuse-t/cask";
        trusted = true;
      }
    ];

    # FUSE-T installs filesystem integration outside the user's home and is
    # intentionally excluded from mise bootstrap ownership.
    casks = [
      "macos-fuse-t/cask/fuse-t"
      "macos-fuse-t/cask/fuse-t-sshfs"
    ];
  };
}
