# nix/modules/darwin/fonts.nix
# System-wide font packages installed via nix-darwin.
{ pkgs, ... }:
{
  fonts.packages = with pkgs; [
    font-awesome
    montserrat
    material-design-icons
    nerd-fonts.dejavu-sans-mono
    nerd-fonts.fira-code
    nerd-fonts.meslo-lg
    nerd-fonts.symbols-only
  ];
}
