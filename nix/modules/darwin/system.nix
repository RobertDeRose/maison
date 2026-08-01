# macOS system configuration. User packages, applications, dotfiles, and
# per-user defaults are deliberately owned by mise.
{
  pkgs,
  user,
  ...
}:
{
  imports = [
    ./fonts.nix
    ./homebrew-system.nix
  ];
  system.primaryUser = user.username;
  users.users.${user.username} = {
    home = "/Users/${user.username}";
    description = user.fullName;
  };

  documentation = {
    enable = false;
    doc.enable = false;
    info.enable = false;
    man.enable = true;
  };

  environment = {
    shells = [ pkgs.zsh ];
    systemPackages = [
      pkgs.deploy-rs
      pkgs.nh
      pkgs.nixd
    ];
  };

  programs.zsh.enable = true;

  # This privileged PAM policy remains in Nix. It must not be converted to a
  # user bootstrap script or a defaults write operation.
  security.pam.services.sudo_local = {
    reattach = true;
    touchIdAuth = true;
    watchIdAuth = true;
  };

  system = {
    defaults.loginwindow.GuestEnabled = false;
    keyboard = {
      enableKeyMapping = true;
      remapCapsLockToEscape = true;
    };
    stateVersion = 6;
  };

  time.timeZone = "America/New_York";
}
